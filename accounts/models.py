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

    groups = models.ManyToManyField(
        'auth.Group',
        related_name='custom_user_groups',
        blank=True,
        verbose_name='Группы'
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='custom_user_permissions',
        blank=True,
        verbose_name='Права'
    )

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return self.username