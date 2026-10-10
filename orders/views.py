from itertools import groupby
from operator import attrgetter
import json
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from accounts.models import Cart, PaymentMethod
from .models import Payment, Order, Transaction
from .services import create_payment_for_checkout, find_payment, capture_payment, refund_payment
from django.contrib import messages
from django.views.decorators.http import require_POST


@login_required
@require_POST
def checkout_view(request):
    cart_items = list(Cart.objects.filter(user=request.user).select_related('publication', 'publication__author'))
    if not cart_items:
        messages.error(request, 'Корзина пуста')
        return redirect('accounts:cart')
    cart_items = [i for i in cart_items if i.publication.author_id != request.user.id]

    if not cart_items:
        messages.error(request, 'Нечего оформлять')
        return redirect('accounts:cart')
    total_amount = sum(i.publication.price for i in cart_items)
    payment = Payment.objects.create(customer=request.user, amount=total_amount, status='pending')
    for item in cart_items:
        publication = item.publication
        Order.objects.create(
            payment=payment,
            customer=request.user,
            executor=publication.author,
            publication=publication,
            title=publication.title,
            description=publication.description,
            amount=publication.price,
            status='pending_payment')
    Cart.objects.filter(user=request.user).delete()

    return redirect('orders:pay_payment', payment_id=payment.id)

# ОПЛАТА
@login_required
@require_POST
def pay_payment_view(request, payment_id):
    """Оплата одного Payment в YooKassa"""
    payment = get_object_or_404(Payment, id=payment_id)
    if payment.customer_id != request.user.id:
        raise PermissionDenied('Это не ваш платёж')
    if payment.status != 'pending':
        raise PermissionDenied('Платёж уже обработан')
    return_url = request.build_absolute_uri(
        reverse('orders:payment_return', kwargs={'payment_id': payment.id}))
    try:
        result = create_payment_for_checkout(payment, return_url)
    except RuntimeError as e:
        messages.error(request, f'Не удалось создать платёж: {e}')
        return redirect('orders:payment_detail', payment_id=payment.id)
    return redirect(result['confirmation_url'])

@login_required
def payment_return_view(request, payment_id):
    """Возврат после оплаты — статус обновится"""
    payment = get_object_or_404(Payment, id=payment_id)
    return render(request, 'orders/payment_return.html', {'payment': payment})


@login_required
def payment_detail_view(request, payment_id):
    """Детали платежа со всеми подзаказами."""
    payment = get_object_or_404(Payment.objects.prefetch_related('orders__transactions'), id=payment_id)
    if payment.customer_id != request.user.id:
        raise PermissionDenied('Это не ваш платёж')
    return render(request, 'orders/payment_detail.html', {'payment': payment})

# ДЕЙСТВИЯ ПО ЗАКАЗАМ
@login_required
@require_POST
def confirm_order_view(request, order_id):
    """Подтвердить конкретный заказ"""
    order = get_object_or_404(Order, id=order_id)
    if order.customer_id != request.user.id:
        raise PermissionDenied('Это не ваш заказ')
    if not order.can_be_confirmed():
        raise PermissionDenied('Нельзя подтвердить в текущем статусе')

    # если платёж был — списываем часть
    if order.payment and order.payment.payment_id:
        try:
            result = capture_payment(order.payment.payment_id, order.amount)
            if getattr(result, 'status', None) != 'succeeded':
                messages.error(request, 'Не удалось списать средства.')
                return redirect('orders:detail', order_id=order.id)
        except Exception as e:
            messages.error(request, f'Ошибка платёжной системы: {e}')
            return redirect('orders:detail', order_id=order.id)

    order.confirm_completion()
    messages.success(request, 'Заказ завершён')
    return redirect('orders:detail', order_id=order.id)


@login_required
@require_POST
def cancel_order_view(request, order_id):
    """Отменить конкретный заказ."""
    order = get_object_or_404(Order, id=order_id)

    if order.customer_id != request.user.id and order.executor_id != request.user.id:
        raise PermissionDenied('Вы не участник этой сделки')
    if not order.can_be_cancelled():
        raise PermissionDenied('Нельзя отменить в текущем статусе')

    if order.payment and order.payment.payment_id and order.status == 'escrow_held':
        try:
            refund_payment(order.payment.payment_id, order.amount)
        except Exception as e:
            messages.error(request, f'Ошибка возврата: {e}')
            return redirect('orders:detail', order_id=order.id)

    order.cancel_and_refund()
    messages.success(request, 'Заказ отменён')
    return redirect('orders:detail', order_id=order.id)


# ============================================================
# СПИСКИ
# ============================================================

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
# ВЕБХУК YOOKASSA
# ============================================================

@csrf_exempt
@require_POST
def yookassa_webhook_view(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest('Invalid JSON')

    event = data.get('event')
    payment_obj = data.get('object', {})
    yookassa_payment_id = payment_obj.get('id')
    metadata = payment_obj.get('metadata', {})
    payment_id = metadata.get('payment_id')

    if not payment_id or not yookassa_payment_id:
        return HttpResponse(status=200)

    payment = Payment.objects.filter(id=payment_id).first()
    if not payment:
        return HttpResponse(status=200)

    if payment.status != 'pending':
        return HttpResponse(status=200)

    # сверяем с YooKassa
    try:
        real_payment = find_payment(yookassa_payment_id)
    except Exception:
        return HttpResponseBadRequest('Payment not found')

    if real_payment.status != 'waiting_for_capture':
        return HttpResponse(status=200)

    if str(real_payment.amount.value) != f'{payment.amount:.2f}':
        return HttpResponseBadRequest('Amount mismatch')

    if event == 'payment.waiting_for_capture':
        payment.status = 'succeeded'
        payment.payment_id = yookassa_payment_id
        payment.save(update_fields=['status', 'payment_id', 'updated_at'])

        Transaction.objects.create(
            payment=payment,
            type='hold',
            status='succeeded',
            amount=payment.amount,
            external_id=yookassa_payment_id,
        )

        # все заказы платежа переходят в escrow_held
        for order in payment.orders.all():
            order.mark_as_escrow_held()

    elif event == 'payment.canceled':
        payment.status = 'failed'
        payment.save(update_fields=['status', 'updated_at'])
        payment.orders.update(status='cancelled')

    return HttpResponse(status=200)