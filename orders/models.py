import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction

class Order(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Черновик'),
        ('pending_payment', 'Ожидает оплаты'),
        ('escrow_held', 'Средства заморожены'),
        ('in_progress', 'В работе'),
        ('pending_review', 'На проверке'),
        ('completed', 'Завершён'),
        ('disputed', 'Спор'),
        ('cancelled', 'Отменён'),
        ('refunded', 'Возвращён')
    )

    # Участники
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='orders_as_customer', verbose_name='Заказчик')
    executor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders_as_executor', verbose_name='Исполнитель')
    # Публикация
    publication = models.ForeignKey('core.Publication', on_delete=models.SET_NULL, null=True, blank=True, related_name='orders', verbose_name='Публикация')
    # Содержание заказа
    title = models.CharField('Название', max_length=200)
    description = models.TextField('Описание', blank=True)
    # Финансы
    amount = models.DecimalField('Сумма', max_digits=10, decimal_places=2)
    platform_fee = models.DecimalField('Комиссия', max_digits=10, decimal_places=2, default=0)
    # Сроки
    deadline = models.DateField('Срок выполнения', null=True, blank=True)
    # Платёж
    payment_id = models.CharField('ID платежа YooKassa', max_length=100, blank=True)
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'
        ordering = ['-created_at']

    def __str__(self):
        return f'Заказ {self.pk}: {self.title}'

    # Бизнес-логика

    def can_be_paid(self):
        return self.status == 'pending_payment'

    def can_be_confirmed(self):
        return self.status in ('in_progress', 'pending_review')

    def can_be_cancelled(self):
        return self.status in ('draft', 'pending_payment', 'escrow_held')

    @transaction.atomic
    def mark_as_escrow_held(self, payment_id):
        """Средства остановлены - деньги на счёте платформы."""
        if self.status != 'pending_payment':
            raise ValidationError('Заказ не ожидает оплаты')

        self.status = 'escrow_held'
        self.payment_id = payment_id
        self.save(update_fields=['status', 'payment_id', 'updated_at'])
        Transaction.objects.create(order=self, type='hold', status='succeeded', amount=self.amount, external_id=payment_id)

    @transaction.atomic
    def confirm_completion(self):
        """Заказчик подтвердил - деньги уходят исполнителю."""
        if not self.can_be_confirmed():
            raise ValidationError('Нельзя подтвердить этот заказ')

        self.status = 'completed'
        self.save(update_fields=['status', 'updated_at'])
        Transaction.objects.create(order=self, type='capture', status='succeeded', amount=self.amount)
        Transaction.objects.create(order=self, type='payout', status='succeeded', amount=self.amount - self.platform_fee)

    @transaction.atomic
    def cancel_and_refund(self):
        """Отмена заказа с возвратом средств"""
        if not self.can_be_cancelled():
            raise ValidationError('Нельзя отменить этот заказ.')
        old_status = self.status
        self.status = 'refunded' if old_status == 'escrow_held' else 'cancelled'
        self.save(update_fields=['status', 'updated_at'])
        if old_status == 'escrow_held':
            Transaction.objects.create(order=self, type='refund', status='succeeded', amount=self.amount)
# Модель:  Финансовая операция по заказу
class Transaction(models.Model):
    TYPE_CHOICES = (
        ('hold', 'Холдирование'),
        ('capture', 'Списание'),
        ('refund', 'Возврат'),
        ('payout', 'Выплата')
    )
    STATUS_CHOICES = (
        ('pending', 'В ожидании'),
        ('succeeded', 'Успешно'),
        ('failed', 'Ошибка')
    )
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='transactions', verbose_name='Заказ')
    type = models.CharField('Тип', max_length=20, choices=TYPE_CHOICES)
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='pending')
    amount = models.DecimalField('Сумма', max_digits=10, decimal_places=2)
    external_id = models.CharField('ID в YooKassa', max_length=100, blank=True)
    idempotence_key = models.UUIDField('Ключ идемпотентности', default=uuid.uuid4, unique=True)

    created_at = models.DateTimeField('Создана', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлена', auto_now=True)

    class Meta:
        verbose_name = 'Транзакция'
        verbose_name_plural = 'Транзакции'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_type_display()} - {self.amount} ₽ ({self.get_status_display()})'