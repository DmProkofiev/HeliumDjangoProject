import json
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .models import Order
from .services import (capture_payment, create_escrow_payment, find_payment, refund_payment)

# CRUD

@login_required
def order_list_view(request):
    as_customer = Order.objects.filter(customer=request.user).select_related('executor', 'publication')
    as_executor = Order.objects.filter(executor=request.user).select_related('customer', 'publication')
    return render(request, 'orders/order_list.html', {'as_customer': as_customer, 'as_executor': as_executor})

@login_required
def order_detail_view(request, order_id):
    order = get_object_or_404(Order.objects.select_related('customer', 'executor', 'publication').prefetch_related('transactions'), id=order_id)
    if request.user.id not in (order.customer_id, order.executor_id):
        raise PermissionDenied('Вы не участник этого заказа')
    return render(request, 'orders/order_detail.html', {'order': order})

@login_required
@require_POST
def pay_order_view(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if order.customer_id != request.user.id:
        raise PermissionDenied('Это не ваш заказ')
    if not order.can_be_paid():
        raise PermissionDenied('Заказ нельзя оплатить в текущем статусе')
    return_url = request.build_absolute_uri(reverse('orders:payment_return', kwargs={'order_id': order.id}))
    try:
        result = create_escrow_payment(order, return_url)
    except RuntimeError as e:
        messages.error(request, f'Не удалось создать платёж: {e}')
        return redirect('orders:detail', order_id=order.id)
    order.payment_id = result['payment_id']
    order.save(update_fields=['payment_id', 'updated_at'])
    return redirect(result['confirmation_url'])

# Возврат
@login_required
def payment_return_view(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if order.customer_id != request.user.id:
        raise PermissionDenied('Это не ваш заказ.')
    return render(request, 'orders/payment_return.html', {'order': order})

# Подтверждение
@login_required
@require_POST
def confirm_order_view(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if order.customer_id != request.user.id:
        raise PermissionDenied('Это не ваш заказ')
    if not order.can_be_confirmed():
        raise PermissionDenied('Заказ нельзя подтвердить в текущем статусе.')
    capture_succeeded = False
    if order.payment_id:
        try:
            result = capture_payment(order.payment_id, order.amount)
            if result.status == 'succeeded':
                capture_succeeded = True
            else:
                messages.error(request,f'Не удалось списать средства (статус: {result.status}). Попробуйте позже')
                return redirect('orders:detail', order_id=order.id)
        except Exception as e:
            messages.error(request, f'Ошибка платёжной системы: {e}')
            return redirect('orders:detail', order_id=order.id)
    order.confirm_completion(capture_succeeded=capture_succeeded)
    messages.success(request, 'Заказ успешно завершён')
    return redirect('orders:detail', order_id=order.id)

# Отмена заказа с возвратом средств
@login_required
@require_POST
def cancel_order_view(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if order.customer_id != request.user.id and order.executor_id != request.user.id:
        raise PermissionDenied('Вы не участник этой сделки')
    if not order.can_be_cancelled():
        raise PermissionDenied('Нельзя отменить в текущем статусе')
    refund_succeeded = False
    if order.payment_id and order.status == 'escrow_held':
        try:
            result = refund_payment(order.payment_id, order.amount)
            if result.status == 'succeeded':
                refund_succeeded = True
            else:
                messages.error(request,f'Не удалось вернуть средства (статус: {result.status}). Попробуйте позже')
                return redirect('orders:detail', order_id=order.id)
        except Exception as e:
                messages.error(request, f'Ошибка платёжной системы: {e}')
                return redirect('orders:detail', order_id=order.id)
    order.cancel_and_refund(refund_succeeded=refund_succeeded)
    messages.success(request, 'Заказ отменён.')
    return redirect('orders:detail', order_id=order.id)

# WebHook YOOKASSA

# Приём уведомлений от YooKassa
@csrf_exempt
@require_POST
def yookassa_webhook_view(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest('Invalid JSON')
    event = data.get('event')
    payment_obj = data.get('object', {})
    payment_id = payment_obj.get('id')
    metadata = payment_obj.get('metadata', {})
    order_id = metadata.get('order_id')
    if not order_id or not payment_id:
        return HttpResponse(status=200)
    order = Order.objects.filter(id=order_id).first()
    if not order:
        return HttpResponse(status=200)
    # Идемпотентность
    if order.status != 'pending_payment':
        return HttpResponse(status=200)
    try:
        real_payment = find_payment(payment_id)
    except Exception:
        return HttpResponseBadRequest('Payment not found in YooKassa')
    if real_payment.status != 'waiting_for_capture':
        return HttpResponse(status=200)
    if str(real_payment.amount.value) != f'{order.amount:.2f}':
        return HttpResponseBadRequest('Amount mismatch')
    if str(real_payment.metadata.get('order_id')) != str(order.id):
        return HttpResponseBadRequest('Order ID mismatch')
    if order.payment_id and order.payment_id != payment_id:
        return HttpResponseBadRequest('Payment ID mismatch')
    if event == 'payment.waiting_for_capture':
        order.mark_as_escrow_held(payment_id)
    elif event == 'payment.canceled':
        order.status = 'cancelled'
        order.save(update_fields=['status', 'updated_at'])
    return HttpResponse(status=200)