import json
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from core.models import Publication
from .forms import UserRegistrationForm, UserUpdateForm, UserLoginForm
from .models import Favorite, Cart, User
from django.contrib import messages
from django.views.decorators.http import require_POST
from .models import PaymentMethod
from django.urls import reverse
from .pay_service import (
    create_binding_payment,
    refund_binding_payment,
    find_payment,
    handle_binding_webhook,
)
from recommendations.logging_service import log_interaction

def login_view(request):
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
    logout(request)
    return redirect('core:feed')

def register_view(request):
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

@login_required
def profile_view(request):
    user = request.user
    my_publications = Publication.objects.filter(author=user).order_by('-created_at')
    favorites = Favorite.objects.filter(user=user).select_related('publication', 'publication__author', 'publication__category')
    cart_items = Cart.objects.filter(user=user).select_related('publication', 'publication__author', 'publication__category')
    payment_methods = user.payment_methods.all()
    context = {
        'my_publications': my_publications,
        'favorites': favorites,
        'cart_items': cart_items,
        'payment_methods': payment_methods,
    }
    return render(request, 'accounts/account_detail.html', context)

@login_required
def profile_edit_view(request):
    if request.method == 'POST':
        form = UserUpdateForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('accounts:account_detail')
    else:
        form = UserUpdateForm(instance=request.user)
    return render(request, 'accounts/profile_edit.html', {'form': form})

def account_user_detail_view(request, username):
    User = get_user_model()
    author = get_object_or_404(User, username=username)
    publications = Publication.objects.filter(author=author,status='active').select_related('category').order_by('-created_at')
    context = {
        'author': author,
        'publications': publications,
    }
    return render(request, 'accounts/account_user_detail.html', context)

@login_required
@require_POST
def toggle_like(request, publication_id):
    publication = get_object_or_404(Publication, id=publication_id)
    like, created = Favorite.objects.get_or_create(user=request.user, publication=publication)
    if not created:
        like.delete()
    else:
        log_interaction(request, 'like', publication=publication)
    is_liked = created
    likes_count = Favorite.objects.filter(publication=publication).count()
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'liked': is_liked, 'likes_count': likes_count})
    return redirect(request.META.get('HTTP_REFERER', 'core:feed'))

@login_required
@require_POST
def toggle_cart(request, publication_id):
    publication = get_object_or_404(Publication, id=publication_id)
    item = Cart.objects.filter(user=request.user, publication=publication).first()
    if item:
        item.delete()
        in_cart = False
    else:
        Cart.objects.create(user=request.user, publication=publication)
        log_interaction(request, 'cart', publication=publication)
        in_cart = True
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'in_cart': in_cart,
            'cart_count': Cart.objects.filter(user=request.user).count(),
        })

    return redirect(request.META.get('HTTP_REFERER') or 'core:feed')

@login_required
@require_POST
def set_default_payment_method_view(request, method_id):
    method = get_object_or_404(PaymentMethod, id=method_id, user=request.user)
    method.is_default = True
    method.save()
    messages.success(request, 'Карта выбрана по умолчанию')
    return redirect('accounts:profile')

@login_required
@require_POST
def remove_payment_method_view(request, method_id):
    method = get_object_or_404(PaymentMethod, id=method_id, user=request.user)
    method.delete()
    messages.success(request, 'Способ оплаты удалён')
    return redirect('accounts:profile')

# Способы оплаты
@login_required
@require_POST
def payment_method_add_view(request):
    method = PaymentMethod.objects.create(user=request.user, is_pending=True)
    return_url = request.build_absolute_uri(reverse('accounts:payment_method_binding_return', kwargs={'method_id': method.id}))
    try:
        result = create_binding_payment(method, return_url)
    except Exception as e:
        method.delete()
        messages.error(request, f'Не удалось начать привязку: {e}')
        return redirect('/accounts/profile/?tab=payments')
    method.payment_method_id = result['payment_id']
    method.save(update_fields=['payment_method_id'])
    return redirect(result['confirmation_url'])

@login_required
def payment_method_binding_return_view(request, method_id):
    """Возврат после оплаты 1 ₽"""
    return redirect('/accounts/profile/?tab=payments')

@login_required
@require_POST
def payment_method_edit_view(request, method_id):
    """Изменение названия карты"""
    method = get_object_or_404(PaymentMethod, id=method_id, user=request.user)
    title = request.POST.get('title', '').strip()
    if len(title) <= 100:
        method.title = title
        method.save(update_fields=['title'])
    return redirect('/accounts/profile/?tab=payments')

@login_required
@require_POST
def payment_method_remove_view(request, method_id):
    """Удаление карты"""
    method = get_object_or_404(PaymentMethod, id=method_id, user=request.user)
    method.delete()
    messages.success(request, 'Способ оплаты удалён')
    return redirect('/accounts/profile/?tab=payments')

@login_required
@require_POST
def payment_method_default_view(request, method_id):
    """Сделать карту основной"""
    method = get_object_or_404(PaymentMethod, id=method_id, user=request.user)
    method.is_default = True
    method.save()
    messages.success(request, 'Карта выбрана по умолчанию')
    return redirect('/accounts/profile/?tab=payments')

# ВЕБХУК YOOKASSA ДЛЯ ПРИВЯЗКИ КАРТЫ
@csrf_exempt
@require_POST
@csrf_exempt
@require_POST
def yookassa_binding_webhook_view(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest('Invalid JSON')
    return handle_binding_webhook(data)
