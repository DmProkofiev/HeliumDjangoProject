import uuid
import json
from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from yookassa import Configuration, Payment as YooPayment, Refund
from .models import PaymentMethod

Configuration.account_id = settings.YOOKASSA_SHOP_ID
Configuration.secret_key = settings.YOOKASSA_SECRET_KEY



# ПРИВЯЗКА КАРТЫ
def create_binding_payment(method, return_url):
    payment = YooPayment.create({
        'amount': {'value': '1.00', 'currency': 'RUB'},
        'capture': True,
        'save_payment_method': True,
        'confirmation': {
            'type': 'redirect',
            'return_url': return_url,
        },
        'description': 'Привязка карты',
        'metadata': {
            'method_id': method.id,
            'user_id': method.user_id,
        },
    }, str(uuid.uuid4()))

    return {
        'payment_id': payment.id,
        'confirmation_url': payment.confirmation.confirmation_url,
    }


def refund_binding_payment(payment_id):
    return Refund.create({
        'payment_id': payment_id,
        'amount': {'value': '1.00', 'currency': 'RUB'},
    }, str(uuid.uuid4()))


def find_payment(payment_id):
    return YooPayment.find_one(payment_id)

# ЛОГИКА ВЕБХУКА ПРИВЯЗКИ

def handle_binding_webhook(data):
    event = data.get('event')
    payment_obj = data.get('object', {})
    yookassa_payment_id = payment_obj.get('id')
    method_id = payment_obj.get('metadata', {}).get('method_id')
    if not method_id or not yookassa_payment_id:
        return HttpResponse(status=200)
    method = PaymentMethod.objects.filter(id=method_id, is_pending=True).first()
    if not method:
        return HttpResponse(status=200)
    try:
        real_payment = find_payment(yookassa_payment_id)
    except Exception:
        return HttpResponseBadRequest('Payment not found')
    if event != 'payment.succeeded':
        return HttpResponse(status=200)
    payment_method_data = getattr(real_payment, 'payment_method', None)
    if not payment_method_data or not getattr(payment_method_data, 'saved', False):
        return HttpResponse(status=200)
    card = getattr(payment_method_data, 'card', None)
    method.payment_method_id = payment_method_data.id
    method.card_last4 = card.last4 if card else ''
    method.card_type = card.card_type if card else ''
    method.title = f'{(card.card_type if card else "Карта")} •••• {(card.last4 if card else "")}'
    method.is_pending = False
    method.save()
    if not method.user.payment_methods.filter(is_pending=False).exclude(pk=method.pk).exists():
        method.is_default = True
        method.save(update_fields=['is_default'])
    try:
        refund_binding_payment(yookassa_payment_id)
    except Exception:
        pass
    return HttpResponse(status=200)