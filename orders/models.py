import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction

class Payment(models.Model):
    STATUS_CHOICES = (('pending', 'Ожидает оплаты'), ('succeeded', 'Оплачен'), ('failed', 'Ошибка'), ('refunded', 'Возвращён'))
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='payments', verbose_name='Покупатель')
    amount = models.DecimalField('Сумма', max_digits=10, decimal_places=2)
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_id = models.CharField('ID платежа YooKassa', max_length=100, blank=True)
    idempotence_key = models.UUIDField('Ключ идемпотентности', default=uuid.uuid4, unique=True)

    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        verbose_name = 'Платёж'
        verbose_name_plural = 'Платежи'
        ordering = ['-created_at']

    def __str__(self):
        return f'Платёж #{self.pk}: {self.amount} ₽'

class Order(models.Model):
    """Один товар от одного продавца - Часть платежа"""

    STATUS_CHOICES = (
        ('pending_payment', 'Ожидает оплаты'),
        ('escrow_held', 'Средства заморожены'),
        ('in_progress', 'В работе'),
        ('pending_review', 'На проверке'),
        ('completed', 'Завершён'),
        ('disputed', 'Спор'),
        ('cancelled', 'Отменён'),
        ('refunded', 'Возвращён'))

    payment = models.ForeignKey(Payment, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders', verbose_name='Платёж')
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='orders_as_customer', verbose_name='Заказчик')
    executor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders_as_executor', verbose_name='Исполнитель')
    publication = models.ForeignKey('core.Publication', on_delete=models.SET_NULL, null=True, blank=True, related_name='orders', verbose_name='Публикация')

    # снимок данных на момент покупки
    title = models.CharField('Название', max_length=200)
    description = models.TextField('Описание', blank=True)
    quantity = models.PositiveIntegerField('Количество', default=1)

    # финансы
    amount = models.DecimalField('Сумма', max_digits=10, decimal_places=2)
    platform_fee = models.DecimalField('Комиссия', max_digits=10, decimal_places=2, default=0)

    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='pending_payment')
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'
        ordering = ['-created_at']

    def __str__(self):
        return f'Заказ #{self.pk}: {self.title}'

    # бизнес-логика

    def can_be_confirmed(self):
        return self.status in ('in_progress', 'pending_review', 'escrow_held')

    def can_be_cancelled(self):
        return self.status in ('pending_payment', 'escrow_held')

    @transaction.atomic
    def mark_as_escrow_held(self):
        """Деньги заморожены — вызывается из вебхука по Payment."""
        if self.status != 'pending_payment':
            return
        self.status = 'escrow_held'
        self.save(update_fields=['status', 'updated_at'])

        Transaction.objects.create(order=self, type='hold', status='succeeded', amount=self.amount)

    @transaction.atomic
    def confirm_completion(self):
        """Подтверждение - деньги уходят исполнителю"""
        if not self.can_be_confirmed():
            raise ValidationError('Нельзя подтвердить этот заказ')

        self.status = 'completed'
        self.save(update_fields=['status', 'updated_at'])

        Transaction.objects.create(order=self, type='capture', status='succeeded', amount=self.amount)
        Transaction.objects.create(order=self, type='payout', status='succeeded', amount=self.amount - self.platform_fee)

    @transaction.atomic
    def cancel_and_refund(self):
        """Отмена с возвратом"""
        if not self.can_be_cancelled():
            raise ValidationError('Нельзя отменить этот заказ')

        old_status = self.status
        self.status = 'refunded' if old_status == 'escrow_held' else 'cancelled'
        self.save(update_fields=['status', 'updated_at'])

        if old_status == 'escrow_held':
            Transaction.objects.create(order=self, type='refund', status='succeeded', amount=self.amount)

class Transaction(models.Model):
    """Финансовая операция"""

    TYPE_CHOICES = (('hold', 'Холдирование'), ('capture', 'Списание'), ('refund', 'Возврат'), ('payout', 'Выплата'))
    STATUS_CHOICES = (('pending', 'В ожидании'), ('succeeded', 'Успешно'), ('failed', 'Ошибка'))

    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, null=True, blank=True, related_name='transactions')
    order = models.ForeignKey(Order, on_delete=models.CASCADE, null=True, blank=True, related_name='transactions')

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