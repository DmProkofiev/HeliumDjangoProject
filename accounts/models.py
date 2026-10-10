from django.contrib.auth.models import AbstractUser
from django.db import models

# Класс пользавателя
class User(AbstractUser):
    ROLE = (
        ('user', 'Пользаватель'),
        ('admin', 'Администратор')
    )
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True, verbose_name='Город')
    role = models.CharField(max_length=10,choices=ROLE,default='user',verbose_name='Роль')
    avatar = models.ImageField('аватар', upload_to='avatars/', blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    groups = models.ManyToManyField('auth.Group', related_name='custom_user_groups', blank=True, verbose_name='Группы')
    user_permissions = models.ManyToManyField('auth.Permission',related_name='custom_user_permissions',blank=True,verbose_name='Права')

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return self.username

# Избранное
class Favorite(models.Model):
    user = models.ForeignKey(User,on_delete=models.CASCADE,related_name='favorites', verbose_name='Пользователь')
    publication = models.ForeignKey('core.Publication',on_delete=models.CASCADE,related_name='favorited_by',verbose_name='Публикация')
    created_at = models.DateTimeField('Добавлено', auto_now_add=True)

    class Meta:
        verbose_name = 'Избранное'
        verbose_name_plural = 'Избранное'
        unique_together = ('user', 'publication')
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user} → {self.publication}'

# Корзина
class Cart(models.Model):
    user = models.ForeignKey(User,on_delete=models.CASCADE,related_name='cart_items',verbose_name='Пользователь')
    publication = models.ForeignKey('core.Publication',on_delete=models.CASCADE,related_name='in_carts',verbose_name='Публикация')
    quantity = models.PositiveIntegerField('Количество', default=1)
    added_at = models.DateTimeField('Добавлено', auto_now_add=True)

    class Meta:
        verbose_name = 'Корзина'
        verbose_name_plural = 'Корзина'
        unique_together = ('user', 'publication')
        ordering = ['-added_at']

    def __str__(self):
        return f'{self.user} → {self.publication} ({self.quantity})'

    @property
    def total(self):
        return self.publication.price * self.quantity

# Способ оплаты
class PaymentMethod(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payment_methods', verbose_name='Пользователь')
    payment_method_id = models.CharField('ID карты в YooKassa', max_length=100, unique=True, null=True, blank=True)
    title = models.CharField('Название', max_length=100, blank=True)
    card_last4 = models.CharField('Последние 4 цифры', max_length=4, blank=True)
    card_type = models.CharField('Тип карты', max_length=20, blank=True)
    is_default = models.BooleanField('По умолчанию', default=False)
    created_at = models.DateTimeField('Добавлена', auto_now_add=True)
    is_verified = models.BooleanField('Проверена', default=True)
    is_pending = models.BooleanField('В процессе привязки', default=False)

    class Meta:
        verbose_name = 'Способ оплаты'
        verbose_name_plural = 'Способы оплаты'
        ordering = ['-is_default', '-created_at']

    def __str__(self):
        return self.title or f'•••• {self.card_last4}'

    def save(self, *args, **kwargs):
        if self.is_default:
            PaymentMethod.objects.filter(user=self.user).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)