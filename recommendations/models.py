from django.db import models
from django.conf import settings

class UserInteraction(models.Model):
    ACTION_CHOICES = (
        ('view', 'Просмотр'),
        ('like', 'Лайк'),
        ('cart', 'В корзину'),
        ('search', 'Поиск'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, verbose_name='Пользователь')
    session_key = models.CharField('Ключ сессии', max_length=40, null=True, blank=True)
    publication = models.ForeignKey('core.Publication', on_delete=models.CASCADE, null=True, blank=True, verbose_name='Публикация')
    action_type = models.CharField('Действие', max_length=10, choices=ACTION_CHOICES)
    search_query = models.CharField('Поисковый запрос', max_length=255, null=True, blank=True)
    created_at = models.DateTimeField('Дата действия', auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Взаимодействие'
        verbose_name_plural = 'Взаимодействия'
        indexes = [
            models.Index(fields=['user', 'action_type']),
            models.Index(fields=['session_key', 'action_type']),
        ]

    def __str__(self):
        subject = self.user.username if self.user else f"Аноним ({self.session_key[:8]}...)"
        target = self.publication.title if self.publication else self.search_query
        return f"{subject} -> {self.get_action_type_display()} -> {target}"