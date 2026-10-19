import json
import logging
import time

from django.contrib import messages
from django.contrib.auth import login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.db.models import Q
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core.forms import PublicationForm
from core.models import Publication
from orders.models import Order
from orders.security import is_yookassa_request
from recommendations.logging_service import log_interaction

from . import administrator_service
from .forms import UserRegistrationForm, UserUpdateForm, UserLoginForm
from .models import Favorite, Cart, User, PaymentMethod
from .pay_service import (
    create_binding_payment,
    handle_binding_webhook,
    find_payment,
    refund_binding_payment,
    sync_binding_from_remote,
)
from .permissions import admin_required, is_admin_user

logger = logging.getLogger(__name__)


# АУТЕНТИФИКАЦИЯ
def login_view(request):
    """Вход по логину и паролю; редирект на next или на ленту."""
    if request.user.is_authenticated:
        return redirect('core:feed')

    form = UserLoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        login(request, user)
        next_url = request.GET.get('next') or request.POST.get('next')
        return redirect(next_url or 'core:feed')

    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    """Выход и редирект на ленту."""
    logout(request)
    return redirect('core:feed')


def register_view(request):
    """Регистрация пользователя; после успеха — автологин."""
    if request.user.is_authenticated:
        return redirect('core:feed')

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('core:feed')
    else:
        form = UserRegistrationForm()

    return render(request, 'accounts/register.html', {'form': form})


# ПРОФИЛЬ

@login_required
def profile_view(request):
    """
    Личный кабинет: публикации, заказы, избранное, корзина, оплата.
    Для администратора добавляет данные для панелей
    «Пользователи» и «Все публикации».
    """
    user = request.user
    is_admin = is_admin_user(user)

    orders = (
        Order.objects
        .filter(Q(customer=user) | Q(executor=user))
        .select_related('customer', 'executor', 'publication', 'payment')
        .order_by('-created_at')
    )

    context = {
        'my_publications': Publication.objects
            .filter(author=user)
            .order_by('-created_at'),
        'favorites': Favorite.objects
            .filter(user=user)
            .select_related('publication', 'publication__author', 'publication__category'),
        'cart_items': Cart.objects
            .filter(user=user)
            .select_related('publication', 'publication__author', 'publication__category'),
        'payment_methods': user.payment_methods.all(),
        'orders': orders,
        'is_admin': is_admin,
    }

    if is_admin:
        admin_search = request.GET.get('admin_search', '').strip()
        admin_status = request.GET.get('admin_status', '').strip()

        admin_users_qs = administrator_service.list_users(admin_search)
        admin_pubs_qs = administrator_service.list_publications(admin_search, admin_status)

        context.update({
            'admin_users': admin_users_qs,
            'admin_users_count': admin_users_qs.count(),
            'admin_publications': admin_pubs_qs,
            'admin_publications_count': admin_pubs_qs.count(),
            'admin_search': admin_search,
            'admin_status': admin_status,
        })

    return render(request, 'accounts/account_detail.html', context)


@login_required
def profile_edit_view(request):
    """Редактирование профиля пользователя."""
    if request.method == 'POST':
        form = UserUpdateForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('accounts:account_detail')
    else:
        form = UserUpdateForm(instance=request.user)

    return render(request, 'accounts/profile_edit.html', {'form': form})


def account_user_detail_view(request, username):
    """Публичный профиль пользователя с активными публикациями."""
    UserModel = get_user_model()
    author = get_object_or_404(UserModel, username=username)
    publications = (
        Publication.objects
        .filter(author=author, status='active')
        .select_related('category')
        .order_by('-created_at')
    )
    return render(request, 'accounts/account_user_detail.html', {
        'author': author,
        'publications': publications,
    })


# ЛАЙКИ И КОРЗИНА

@login_required
@require_POST
def toggle_like(request, publication_id):
    """Переключает лайк публикации."""
    publication = get_object_or_404(Publication, id=publication_id)
    like, created = Favorite.objects.get_or_create(
        user=request.user, publication=publication,
    )
    if not created:
        like.delete()
    else:
        try:
            log_interaction(request, 'like', publication=publication)
        except Exception:
            logger.exception('log_interaction failed on like')

    likes_count = Favorite.objects.filter(publication=publication).count()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'liked': created, 'likes_count': likes_count})

    return redirect(request.META.get('HTTP_REFERER', 'core:feed'))


@login_required
@require_POST
def toggle_cart(request, publication_id):
    """Переключает наличие публикации в корзине."""
    publication = get_object_or_404(Publication, id=publication_id)
    in_cart = False

    try:
        Cart.objects.create(user=request.user, publication=publication)
        in_cart = True
        try:
            log_interaction(request, 'cart', publication=publication)
        except Exception:
            logger.exception('log_interaction failed on cart')
    except IntegrityError:
        Cart.objects.filter(user=request.user, publication=publication).delete()
        in_cart = False

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'in_cart': in_cart,
            'cart_count': Cart.objects.filter(user=request.user).count(),
        })

    return redirect(request.META.get('HTTP_REFERER') or 'core:feed')


# СПОСОБЫ ОПЛАТЫ

@login_required
@require_POST
def payment_method_add_view(request):
    """Создаёт PaymentMethod в is_pending=True и инициирует привязку."""
    method = PaymentMethod.objects.create(user=request.user, is_pending=True)
    return_url = request.build_absolute_uri(
        reverse(
            'accounts:payment_method_binding_return',
            kwargs={'method_id': method.id},
        )
    )
    try:
        result = create_binding_payment(method, return_url)
    except Exception as exc:
        method.delete()
        messages.error(request, f'Не удалось начать привязку: {exc}')
        return redirect('/accounts/profile/?tab=payments')

    method.payment_method_id = result['payment_id']
    method.save(update_fields=['payment_method_id'])
    return redirect(result['confirmation_url'])


def _try_sync_binding(method, attempts=3, delay=1.0):
    """Пробует синхронизировать привязку несколько раз подряд."""
    for i in range(attempts):
        try:
            real = find_payment(method.payment_method_id)
            if sync_binding_from_remote(method, real):
                return True
        except Exception:
            logger.exception('sync attempt %d failed for method #%s', i, method.id)
        if i < attempts - 1:
            time.sleep(delay)
    return False


@login_required
def payment_method_binding_return_view(request, method_id):
    """Возврат из YooKassa после привязки карты."""
    method = get_object_or_404(PaymentMethod, id=method_id, user=request.user)

    if method.is_pending and method.payment_method_id:
        synced = _try_sync_binding(method, attempts=3, delay=1.0)
        if synced:
            try:
                refund_binding_payment(method.payment_method_id)
            except Exception:
                logger.exception('Возврат 1 ₽ не удался для method #%s', method.id)
            messages.success(request, 'Карта успешно привязана')
        else:
            messages.info(
                request,
                'YooKassa ещё обрабатывает привязку. '
                'Нажмите «Проверить статус» через минуту.',
            )

    return redirect('/accounts/profile/?tab=payments')


@login_required
@require_POST
def payment_method_check_binding_view(request, method_id):
    """Ручная повторная синхронизация pending-карты."""
    method = get_object_or_404(PaymentMethod, id=method_id, user=request.user)

    if not method.is_pending:
        messages.info(request, 'Карта уже привязана')
        return redirect('/accounts/profile/?tab=payments')

    if not method.payment_method_id:
        messages.error(request, 'У карты отсутствует идентификатор YooKassa. Удалите и добавьте заново.')
        return redirect('/accounts/profile/?tab=payments')

    try:
        real = find_payment(method.payment_method_id)
    except Exception:
        logger.exception('Check binding: cannot fetch payment for method #%s', method.id)
        messages.error(request, 'Не удалось запросить YooKassa. Попробуйте позже.')
        return redirect('/accounts/profile/?tab=payments')

    remote_status = getattr(real, 'status', None)

    if remote_status == 'succeeded' and sync_binding_from_remote(method, real):
        try:
            refund_binding_payment(method.payment_method_id)
        except Exception:
            logger.exception('Check binding: refund failed for method #%s', method.id)
        messages.success(request, 'Карта успешно привязана')
        return redirect('/accounts/profile/?tab=payments')

    if remote_status == 'canceled':
        method.delete()
        messages.error(request, 'Привязка карты была отменена или не удалась. Карта удалена.')
        return redirect('/accounts/profile/?tab=payments')

    messages.warning(
        request,
        f'YooKassa ещё не подтвердила карту (статус: {remote_status or "неизвестен"}). '
        f'Попробуйте снова через минуту.',
    )
    return redirect('/accounts/profile/?tab=payments')


@login_required
@require_POST
def payment_method_edit_view(request, method_id):
    """Изменение отображаемого названия карты."""
    method = get_object_or_404(PaymentMethod, id=method_id, user=request.user)
    title = request.POST.get('title', '').strip()
    if len(title) <= 100:
        method.title = title
        method.save(update_fields=['title'])
    return redirect('/accounts/profile/?tab=payments')


@login_required
@require_POST
def payment_method_remove_view(request, method_id):
    """Удаление сохранённого способа оплаты."""
    method = get_object_or_404(PaymentMethod, id=method_id, user=request.user)
    method.delete()
    messages.success(request, 'Способ оплаты удалён')
    return redirect('/accounts/profile/?tab=payments')


@login_required
@require_POST
def payment_method_default_view(request, method_id):
    """Установка способа оплаты по умолчанию."""
    method = get_object_or_404(PaymentMethod, id=method_id, user=request.user)
    method.is_default = True
    method.save()
    messages.success(request, 'Карта выбрана по умолчанию')
    return redirect('/accounts/profile/?tab=payments')


# ВЕБХУК YOOKASSA ДЛЯ ПРИВЯЗКИ
@csrf_exempt
@require_POST
def yookassa_binding_webhook_view(request):
    """Вебхук для привязки карт с обязательной проверкой IP"""
    if not is_yookassa_request(request):
        logger.warning('Binding webhook: forbidden source')
        return HttpResponseForbidden('Forbidden')
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest('Invalid JSON')
    return handle_binding_webhook(data)

# АДМИНИСТРИРОВАНИЕ: ПОЛЬЗОВАТЕЛИ
@admin_required
@require_POST
def admin_toggle_user_block_view(request, user_id):
    try:
        target = administrator_service.toggle_user_block(request.user, user_id)
    except User.DoesNotExist:
        messages.error(request, 'Пользователь не найден')
        return redirect('/accounts/profile/?tab=admin-users')
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect('/accounts/profile/?tab=admin-users')

    action = 'разблокирован' if target.is_active else 'заблокирован'
    messages.success(request, f'Пользователь «{target.username}» {action}')
    return redirect('/accounts/profile/?tab=admin-users')

# АДМИНИСТРИРОВАНИЕ: ПУБЛИКАЦИИ
@admin_required
@require_POST
def admin_freeze_publication_view(request, slug):
    try:
        publication, changed = administrator_service.freeze_publication(request.user, slug)
    except Publication.DoesNotExist:
        messages.error(request, 'Публикация не найдена')
        return redirect('/accounts/profile/?tab=admin-publications')

    if changed:
        messages.success(request, f'Публикация «{publication.title}» заморожена')
    else:
        messages.info(request, 'Публикация уже заморожена')
    return redirect('/accounts/profile/?tab=admin-publications')


@admin_required
@require_POST
def admin_unfreeze_publication_view(request, slug):
    try:
        publication, changed = administrator_service.unfreeze_publication(request.user, slug)
    except Publication.DoesNotExist:
        messages.error(request, 'Публикация не найдена')
        return redirect('/accounts/profile/?tab=admin-publications')

    if changed:
        messages.success(request, f'Публикация «{publication.title}» разморожена')
    else:
        messages.info(request, 'Публикация не была заморожена')
    return redirect('/accounts/profile/?tab=admin-publications')

@admin_required
@require_POST
def admin_delete_publication_view(request, slug):
    try:
        title = administrator_service.delete_publication(request.user, slug)
    except Publication.DoesNotExist:
        messages.error(request, 'Публикация не найдена')
        return redirect('/accounts/profile/?tab=admin-publications')

    messages.success(request, f'Публикация «{title}» удалена')
    return redirect('/accounts/profile/?tab=admin-publications')

@admin_required
def admin_publication_update_view(request, slug):
    try:
        publication = administrator_service.get_publication_for_admin_edit(
            request.user, slug,
        )
    except Publication.DoesNotExist:
        messages.error(request, 'Публикация не найдена')
        return redirect('/accounts/profile/?tab=admin-publications')

    if request.method == 'POST':
        form = PublicationForm(request.POST, request.FILES, instance=publication)
        files = request.FILES.getlist('images_upload')
        if form.is_valid():
            administrator_service.update_publication(
                request.user, publication, form, files,
            )
            messages.success(request, 'Изменения сохранены')
            return redirect('/accounts/profile/?tab=admin-publications')
    else:
        form = PublicationForm(instance=publication)

    return render(request, 'core/publication_form.html', {
        'form': form,
        'publication': publication,
        'is_edit': True,
        'is_admin_edit': True,
    })