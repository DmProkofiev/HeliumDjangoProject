import json
import logging
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from accounts.models import Cart
from .models import Payment, Order, Transaction
from .services import (
    create_payment_for_checkout,
    find_payment,
    capture_payment,
    refund_payment,
)

logger = logging.getLogger(__name__)

# ОФОРМЛЕНИЕ ЗАКАЗА
@login_required
@require_POST
@login_required
@require_POST
def checkout_view(request):
    with transaction.atomic():
        cart_items = list(
            Cart.objects
            .select_for_update()
            .filter(user=request.user)
            .select_related('publication', 'publication__author')
        )
        cart_items = [i for i in cart_items if i.publication.author_id != request.user.id]
        if not cart_items:
            messages.error(request, 'Корзина пуста')
            return redirect('/accounts/profile/?tab=cart')
        total_amount = sum(
            (i.publication.price or Decimal('0')) * i.quantity
            for i in cart_items
        )
        if total_amount <= 0:
            messages.error(request, 'Некорректная сумма заказа')
            return redirect('/accounts/profile/?tab=cart')
        payment = Payment.objects.create(
            customer=request.user,
            amount=total_amount,
            status='pending',
        )
        for item in cart_items:
            pub = item.publication
            Order.objects.create(
                payment=payment,
                customer=request.user,
                executor=pub.author,
                publication=pub,
                title=pub.title,
                description=pub.description,
                quantity=item.quantity,
                amount=(pub.price or Decimal('0')) * item.quantity,
                status='pending_payment',
            )
        Cart.objects.filter(id__in=[i.id for i in cart_items]).delete()
    logger.info(
        'Checkout: payment #%s created for user %s, amount=%s',
        payment.id, request.user.id, total_amount,
    )
    #ПЛАТЕЖ В ЮKASSA
    return_url = request.build_absolute_uri(
        reverse('orders:payment_return', kwargs={'payment_id': payment.id})
    )
    try:
        result = create_payment_for_checkout(payment, return_url)
    except RuntimeError as e:
        logger.exception('Failed to create YooKassa payment for Payment #%s', payment.id)
        messages.error(request, f'Не удалось создать платёж: {e}')
        return redirect('orders:payment_detail', payment_id=payment.id)
    return redirect(result['confirmation_url'])

# ОПЛАТА
@login_required
@require_POST
def pay_payment_view(request, payment_id):
    payment = get_object_or_404(Payment, id=payment_id)
    if payment.customer_id != request.user.id:
        raise PermissionDenied('Это не ваш платёж')
    if payment.status != 'pending':
        raise PermissionDenied('Платёж уже обработан')
    if not payment.orders.exists():
        messages.error(request, 'Платёж не содержит заказов')
        return redirect('orders:payment_detail', payment_id=payment.id)
    return_url = request.build_absolute_uri(
        reverse('orders:payment_return', kwargs={'payment_id': payment.id})
    )
    try:
        result = create_payment_for_checkout(payment, return_url)
    except RuntimeError as e:
        logger.exception('Failed to create YooKassa payment for Payment #%s', payment.id)
        messages.error(request, f'Не удалось создать платёж: {e}')
        return redirect('orders:payment_detail', payment_id=payment.id)
    return redirect(result['confirmation_url'])


@login_required
def payment_return_view(request, payment_id):
    payment = get_object_or_404(Payment, id=payment_id)
    if payment.customer_id != request.user.id:
        raise PermissionDenied('Это не ваш платёж')
    if payment.status == 'pending' and payment.payment_id:
        try:
            real = find_payment(payment.payment_id)
            _sync_payment_state(payment, real)
            payment.refresh_from_db()
        except Exception:
            logger.exception('Fallback sync failed for Payment #%s', payment.id)

    return render(request, 'orders/payment_return.html', {'payment': payment})

@login_required
def payment_detail_view(request, payment_id):
    payment = get_object_or_404(
        Payment.objects.prefetch_related('orders__transactions'),
        id=payment_id,
    )
    if payment.customer_id != request.user.id:
        raise PermissionDenied('Это не ваш платёж')
    return render(request, 'orders/payment_detail.html', {'payment': payment})


# ДЕЙСТВИЯ ПО ЗАКАЗАМ
@login_required
@require_POST
def confirm_order_view(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if order.customer_id != request.user.id:
        raise PermissionDenied('Это не ваш заказ')
    if not order.can_be_confirmed():
        raise PermissionDenied('Нельзя подтвердить в текущем статусе')
    order.confirm_completion()
    logger.info('Order #%s confirmed by customer %s', order.id, request.user.id)
    messages.success(request, 'Заказ завершён')
    return redirect('orders:detail', order_id=order.id)

@login_required
@require_POST
def cancel_order_view(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if order.customer_id != request.user.id and order.executor_id != request.user.id:
        raise PermissionDenied('Вы не участник этой сделки')
    if not order.can_be_cancelled():
        raise PermissionDenied('Нельзя отменить в текущем статусе')

    if order.payment and order.payment.payment_id and order.status == 'escrow_held':
        try:
            refund_payment(order.payment.payment_id, order.amount)
        except Exception as e:
            logger.exception('Refund failed for Order #%s', order.id)
            messages.error(request, f'Ошибка возврата: {e}')
            return redirect('orders:detail', order_id=order.id)

    order.cancel_and_refund()
    logger.info('Order #%s cancelled and refunded', order.id)
    messages.success(request, 'Заказ отменён')
    return redirect('orders:detail', order_id=order.id)

# СПИСКИ
@login_required
def order_list_view(request):
    as_customer = Order.objects.filter(
        customer=request.user
    ).select_related('executor', 'publication', 'payment').order_by('-created_at')

    as_executor = Order.objects.filter(
        executor=request.user
    ).select_related('customer', 'publication', 'payment').order_by('-created_at')

    return render(request, 'orders/order_list.html', {
        'as_customer': as_customer,
        'as_executor': as_executor,
    })


@login_required
def order_detail_view(request, order_id):
    order = get_object_or_404(
        Order.objects.select_related('customer', 'executor', 'publication', 'payment')
                      .prefetch_related('transactions'),
        id=order_id,
    )
    if request.user.id not in (order.customer_id, order.executor_id):
        raise PermissionDenied('Вы не участник этого заказа')
    return render(request, 'orders/order_detail.html', {'order': order})


# ============================================================
# ЕДИНЫЙ ВЕБХУК YOOKASSA
# ============================================================

@csrf_exempt
@require_POST
def yookassa_webhook_view(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest('Invalid JSON')
    obj = data.get('object', {})
    yookassa_payment_id = obj.get('id')
    metadata = obj.get('metadata', {})
    if 'method_id' in metadata:
        from accounts.pay_service import handle_binding_webhook
        return handle_binding_webhook(data)

    if 'payment_id' not in metadata or not yookassa_payment_id:
        return HttpResponse(status=200)
    payment = Payment.objects.filter(id=metadata['payment_id']).first()
    if not payment:
        logger.warning('Webhook: Payment #%s not found', metadata['payment_id'])
        return HttpResponse(status=200)
    if payment.status == 'succeeded':
        return HttpResponse(status=200)
    try:
        real = find_payment(yookassa_payment_id)
    except Exception:
        logger.exception('Webhook: cannot fetch YooKassa payment %s', yookassa_payment_id)
        return HttpResponseBadRequest('Payment not found')
    return _sync_payment_state(payment, real)

def _sync_payment_state(payment, real_payment):
    # Проверка суммы — через Decimal, не через str
    try:
        real_amount = Decimal(str(real_payment.amount.value))
    except (AttributeError, InvalidOperation, ValueError):
        logger.error('Invalid YooKassa amount for Payment #%s', payment.id)
        return HttpResponseBadRequest('Invalid amount')
    if real_amount != payment.amount:
        logger.error(
            'Amount mismatch for Payment #%s: DB=%s, YooKassa=%s',
            payment.id, payment.amount, real_amount,
        )
        return HttpResponseBadRequest('Amount mismatch')
    status = getattr(real_payment, 'status', None)
    # Отмена
    if status == 'canceled':
        with transaction.atomic():
            p = Payment.objects.select_for_update().get(id=payment.id)
            if p.status == 'pending':
                p.status = 'failed'
                p.save(update_fields=['status', 'updated_at'])
                p.orders.update(status='cancelled')
        logger.info('Payment #%s canceled', payment.id)
        return HttpResponse(status=200)
    #Холдирование capture на полную сумму
    if status == 'waiting_for_capture':
        try:
            capture_payment(real_payment.id, payment.amount)
            logger.info(
                'Captured YooKassa payment %s for %s',
                real_payment.id, payment.amount,
            )
        except Exception as e:
            logger.exception('Capture failed for Payment #%s', payment.id)
            return HttpResponseBadRequest(f'Capture failed: {e}')
        try:
            real_payment = find_payment(real_payment.id)
        except Exception:
            logger.exception('Re-fetch after capture failed for Payment #%s', payment.id)
            return HttpResponse(status=200)
        status = getattr(real_payment, 'status', None)
    if status == 'succeeded':
        _finalize_payment_success(payment, real_payment.id)
    return HttpResponse(status=200)


def _finalize_payment_success(payment, yookassa_payment_id):
    with transaction.atomic():
        p = Payment.objects.select_for_update().get(id=payment.id)
        if p.status == 'succeeded':
            return
        p.status = 'succeeded'
        if not p.payment_id:
            p.payment_id = yookassa_payment_id
        p.save(update_fields=['status', 'payment_id', 'updated_at'])
        Transaction.objects.create(
            payment=p,
            type='hold',
            status='succeeded',
            amount=p.amount,
            external_id=yookassa_payment_id,
        )
        for order in p.orders.all():
            order.mark_as_escrow_held()
        pub_ids = list(p.orders.values_list('publication_id', flat=True))
        Cart.objects.filter(user=p.customer, publication_id__in=pub_ids).delete()
    logger.info('Payment #%s finalized, orders moved to escrow_held', payment.id)