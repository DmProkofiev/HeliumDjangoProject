import uuid
from django.conf import settings
from yookassa import Configuration, Payment as YooPayment, Refund
from .models import Transaction
Configuration.account_id = settings.YOOKASSA_SHOP_ID
Configuration.secret_key = settings.YOOKASSA_SECRET_KEY

# СОЗДАНИЕ ПЛАТЕЖА ЗА КОРЗИНУ
def create_payment_for_checkout(payment, return_url):
    try:
        yookassa_payment = YooPayment.create({
            'amount': {
                'value': f'{payment.amount:.2f}',
                'currency': 'RUB',
            },
            'capture': False,
            'confirmation': {
                'type': 'redirect',
                'return_url': return_url,
            },
            'description': f'Оплата {payment.orders.count()} товаров',
            'metadata': {
                'payment_id': payment.id,
            },
        }, str(payment.idempotence_key))
    except Exception as e:
        payment.status = 'failed'
        payment.save(update_fields=['status', 'updated_at'])
        raise RuntimeError(f'YooKassa error: {e}') from e
    payment.payment_id = yookassa_payment.id
    payment.save(update_fields=['payment_id', 'updated_at'])
    return {'payment_id': yookassa_payment.id, 'confirmation_url': yookassa_payment.confirmation.confirmation_url, 'status': yookassa_payment.status}

# ХОЛДИРОВАНИЕ
def create_escrow_payment(order, return_url):
    """
    Создаёт платёж на один Order
    Используется, когда заказ создан напрямую
    """
    tx = Transaction.objects.filter(order=order, type='hold', status='pending').order_by('-created_at').first()

    if tx is None:
        tx = Transaction.objects.create(order=order, type='hold', status='pending', amount=order.amount)
    try:
        payment = YooPayment.create({
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

    return {
        'payment_id': payment.id,
        'confirmation_url': payment.confirmation.confirmation_url,
        'status': payment.status,
    }

# СПИСАНИЕ (CAPTURE)
def capture_payment(payment_id, amount):
    """Списание средств"""
    return YooPayment.capture(
        payment_id,
        {
            'amount': {
                'value': f'{amount:.2f}',
                'currency': 'RUB',
            },
        },
        str(uuid.uuid4()),
    )

# ВОЗВРАТ (REFUND)
def refund_payment(payment_id, amount):
    """Возврат средств покупателю"""
    return Refund.create({
        'payment_id': payment_id,
        'amount': {
            'value': f'{amount:.2f}',
            'currency': 'RUB',
        },
    })

# ПРОВЕРКА ПЛАТЕЖА
def find_payment(payment_id):
    return YooPayment.find_one(payment_id)