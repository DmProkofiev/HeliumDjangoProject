import uuid
from decimal import Decimal
from django.conf import settings
from yookassa import Configuration, Payment, Refund
from orders.models import Transaction

Configuration.account_id = settings.YOOKASSA_SHOP_ID
Configuration.secret_key = settings.YOOKASSA_SECRET_KEY

# Создать платежное поручение
def create_escrow_payment(order, return_url):
    tx = Transaction.objects.filter(order=order, type='hold', status='pending').order_by('-created_at').first()
    if tx is None:
        tx = Transaction.objects.create(
            order=order,
            type='hold',
            status='pending',
            amount=order.amount,
        )
    try:
        payment = Payment.create({
            'amount': {
                'value': f'{order.amount:.2f}',
                'currency': 'RUB',
            },
            'capture': False,
            'confirmation': {
                'type': 'redirect',
                'return_url': return_url,
            },
            'description': f'Оплата заказа №{order.id}',
            'metadata': {
                'order_id': order.id,
            },
        }, str(tx.idempotence_key))
    except Exception as e:
        tx.status = 'failed'
        tx.save(update_fields=['status', 'updated_at'])
        raise RuntimeError(f'YooKassa error: {e}') from e

    tx.external_id = payment.id
    tx.save(update_fields=['external_id', 'updated_at'])
    return {'payment_id': payment.id, 'confirmation_url': payment.confirmation.confirmation_url, 'status': payment.status}

# Выполнить платежное поручение
def capture_payment(payment_id, amount):
    return Payment.capture(
        payment_id,
        {
            'amount': {
                'value': f'{amount:.2f}',
                'currency': 'RUB',
            },
        },
        str(uuid.uuid4()),
    )

# Отменить платежное поручение
def refund_payment(payment_id, amount):
    return Refund.create({
        'payment_id': payment_id,
        'amount': {
            'value': f'{amount:.2f}',
            'currency': 'RUB',
        },
    })

# Проверка платежного поручения
def find_payment(payment_id):
    return Payment.find_one(payment_id)