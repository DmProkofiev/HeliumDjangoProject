import uuid
import logging
from django.conf import settings
from yookassa import Configuration, Payment as YooPayment, Refund
from .models import Transaction

logger = logging.getLogger(__name__)

Configuration.account_id = settings.YOOKASSA_SHOP_ID
Configuration.secret_key = settings.YOOKASSA_SECRET_KEY


def _assert_our_recipient(remote_object):
    """
    Проверяет, что платёж/возврат принадлежит нашему магазину.
    Защита от подделки вебхука чужим магазином.
    Возвращает True, если проверка пройдена (или поле отсутствует в ответе).
    """
    recipient = getattr(remote_object, 'recipient', None)
    if not recipient:
        return True
    account_id = getattr(recipient, 'account_id', None)
    if account_id is None:
        return True
    return account_id == settings.YOOKASSA_SHOP_ID


def create_payment_for_checkout(payment, return_url):
    """
    Создаёт в YooKassa единый платёж за корзину (Payment собирает несколько Order).
    Использует payment.idempotence_key — повторный вызов вернёт тот же платёж.

    ВАЖНО: при идемпотентном ответе, когда платёж уже прошёл стадию pending
    (waiting_for_capture / succeeded / canceled), в ответе YooKassa отсутствует
    поле confirmation — поэтому confirmation_url читается безопасно и может
    быть None. Вызывающий код решает, что делать по полю status.
    """
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
    except Exception as exc:
        payment.status = 'failed'
        payment.save(update_fields=['status', 'updated_at'])
        raise RuntimeError(f'YooKassa error: {exc}') from exc

    payment.payment_id = yookassa_payment.id
    payment.save(update_fields=['payment_id', 'updated_at'])

    # Безопасное чтение confirmation: при идемпотентном ответе
    # confirmation может отсутствовать (None) — берём через getattr.
    confirmation = getattr(yookassa_payment, 'confirmation', None)
    confirmation_url = (
        getattr(confirmation, 'confirmation_url', None)
        if confirmation is not None
        else None
    )

    return {
        'payment_id': yookassa_payment.id,
        'confirmation_url': confirmation_url,
        'status': yookassa_payment.status,
    }


def create_escrow_payment(order, return_url):
    """
    Создаёт платёж под один Order (сценарий прямой оплаты без корзины)
    Идемпотентность — через Transaction.idempotence_key
    """
    tx = (
        Transaction.objects
        .filter(order=order, type='hold', status='pending')
        .order_by('-created_at')
        .first()
    )
    if tx is None:
        tx = Transaction.objects.create(
            order=order, type='hold', status='pending', amount=order.amount,
        )

    try:
        payment = YooPayment.create({
            'amount': {'value': f'{order.amount:.2f}', 'currency': 'RUB'},
            'capture': False,
            'confirmation': {'type': 'redirect', 'return_url': return_url},
            'description': f'Оплата заказа №{order.id}',
            'metadata': {'order_id': order.id},
        }, str(tx.idempotence_key))
    except Exception as exc:
        tx.status = 'failed'
        tx.save(update_fields=['status', 'updated_at'])
        raise RuntimeError(f'YooKassa error: {exc}') from exc

    tx.external_id = payment.id
    tx.save(update_fields=['external_id', 'updated_at'])

    confirmation = getattr(payment, 'confirmation', None)
    confirmation_url = (
        getattr(confirmation, 'confirmation_url', None)
        if confirmation is not None
        else None
    )

    return {
        'payment_id': payment.id,
        'confirmation_url': confirmation_url,
        'status': payment.status,
    }

def capture_payment(payment_id, amount):
    """Списывает ранее холдированные средства"""
    return YooPayment.capture(
        payment_id,
        {'amount': {'value': f'{amount:.2f}', 'currency': 'RUB'}},
        str(uuid.uuid4()),
    )

def refund_payment(payment_id, amount):
    """Возвращает средства покупателю"""
    return Refund.create({
        'payment_id': payment_id,
        'amount': {'value': f'{amount:.2f}', 'currency': 'RUB'},
    })


def find_payment(payment_id):
    """Запрашивает платёж из YooKassa по его идентификатору"""
    return YooPayment.find_one(payment_id)