import uuid
from django.conf import settings
from yookassa import Configuration, Payment as YooPayment, Refund

Configuration.account_id = settings.YOOKASSA_SHOP_ID
Configuration.secret_key = settings.YOOKASSA_SECRET_KEY

def create_binding_payment(method, return_url):
    """
    Создаёт платёж на 1 ₽ с сохранением карты
    Привязывает карту к существующей PaymentMethod (is_pending=True)
    """
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
    """Возврат 1 ₽ после привязки"""
    return Refund.create({
        'payment_id': payment_id,
        'amount': {'value': '1.00', 'currency': 'RUB'},
    }, str(uuid.uuid4()))

def find_payment(payment_id):
    return YooPayment.find_one(payment_id)