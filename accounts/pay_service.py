import uuid
import logging

from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest
from yookassa import Configuration, Payment as YooPayment, Refund

from .models import PaymentMethod

logger = logging.getLogger(__name__)

Configuration.account_id = settings.YOOKASSA_SHOP_ID
Configuration.secret_key = settings.YOOKASSA_SECRET_KEY


def create_binding_payment(method, return_url):
    """
    Создаёт в YooKassa платёж на 1 рубль с save_payment_method=True.
    capture=True — деньги списываются сразу; после успешной привязки
    мы возвращаем 1 ₽ через refund_binding_payment.
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
    """
    Возвращает 1 рубль после успешной привязки карты.

    Идемпотентность: ключ строится от payment_id, поэтому повторный
    вызов (например, вебхук + возврат с YooKassa) не создаст второй
    возврат — YooKassa вернёт тот же результат.
    """
    return Refund.create({
        'payment_id': payment_id,
        'amount': {'value': '1.00', 'currency': 'RUB'},
    }, f'refund-binding-{payment_id}')


def find_payment(payment_id):
    """Запрашивает платёж в YooKassa для сверки статуса."""
    return YooPayment.find_one(payment_id)


def sync_binding_from_remote(method, real_payment):
    """
    Заполняет PaymentMethod данными карты из объекта YooKassa Payment.

    Возвращает True, только если:
    - платёж в статусе 'succeeded';
    - в платеже есть сохранённый payment_method.

    В противном случае — False, метод остаётся is_pending=True,
    и пользователь/вебхук могут повторить попытку позже.
    """
    remote_status = getattr(real_payment, 'status', None)
    if remote_status != 'succeeded':
        logger.info(
            'sync_binding_from_remote: платёж %s в статусе %s, ждём succeeded',
            getattr(real_payment, 'id', '?'), remote_status,
        )
        return False

    payment_method_data = getattr(real_payment, 'payment_method', None)
    if not payment_method_data or not getattr(payment_method_data, 'saved', False):
        logger.info(
            'sync_binding_from_remote: платёж %s не содержит сохранённой карты',
            getattr(real_payment, 'id', '?'),
        )
        return False

    card = getattr(payment_method_data, 'card', None)
    card_last4 = getattr(card, 'last4', '') or ''
    card_type = getattr(card, 'card_type', '') or ''

    method.payment_method_id = payment_method_data.id
    method.card_last4 = card_last4
    method.card_type = card_type
    method.title = f'{card_type or "Карта"} •••• {card_last4}'
    method.is_pending = False
    method.save()

    # Первая подтверждённая карта автоматически становится основной.
    if not method.user.payment_methods.filter(is_pending=False).exclude(pk=method.pk).exists():
        method.is_default = True
        method.save(update_fields=['is_default'])

    logger.info(
        'Карта привязана для user_id=%s (method #%s, %s •••• %s)',
        method.user_id, method.id, card_type or 'Карта', card_last4 or '????',
    )
    return True


def handle_binding_webhook(data):
    """
    Обрабатывает вебхук привязки карты.
    Требует:
    - event == payment.succeeded;
    - metadata.method_id указывает на существующий PaymentMethod в is_pending=True;
    - запрос пришёл с IP YooKassa (проверяется в views);
    - платёж принадлежит нашему магазину.
    """
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
        logger.exception('Binding: payment %s not found', yookassa_payment_id)
        return HttpResponseBadRequest('Payment not found')

    recipient = getattr(real_payment, 'recipient', None)
    if recipient:
        account_id = getattr(recipient, 'account_id', None)
        if account_id and account_id != settings.YOOKASSA_SHOP_ID:
            logger.error('Binding: recipient mismatch for method #%s', method_id)
            return HttpResponseBadRequest('Recipient mismatch')

    if event != 'payment.succeeded':
        return HttpResponse(status=200)

    if not sync_binding_from_remote(method, real_payment):
        return HttpResponse(status=200)

    # Возврат 1 ₽ — best effort; повторный вызов идемпотентен.
    try:
        refund_binding_payment(yookassa_payment_id)
    except Exception:
        logger.exception('Binding: refund failed for payment %s', yookassa_payment_id)

    return HttpResponse(status=200)