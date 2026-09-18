from django.conf import settings
from django.db import models
from django.db.models import Q


class Chat(models.Model):

    user1 = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chats_as_user1', verbose_name='Участник 1',)
    user2 = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chats_as_user2', verbose_name='Участник 2',)
    publication = models.ForeignKey('core.Publication', on_delete=models.SET_NULL, null=True, blank=True, related_name='chats', verbose_name='Публикация',)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        verbose_name = 'Диалог'
        verbose_name_plural = 'Диалоги'
        ordering = ['-updated_at']

    def __str__(self):
        return f'Диалог #{self.pk}: {self.user1} ↔ {self.user2}'

    def has_participant(self, user):
        return user.is_authenticated and user.id in (self.user1_id, self.user2_id)

    def get_other_user(self, user):
        if user.id == self.user1_id:
            return self.user2
        if user.id == self.user2_id:
            return self.user1
        return None

    def last_message(self):
        return self.messages.order_by('-created_at').first()

    def unread_count_for(self, user):
        return self.messages.filter(is_read=False).exclude(author=user).count()

    @classmethod
    def get_or_create_between(cls, user_a, user_b, publication=None):
        if user_a.id == user_b.id:
            raise ValueError('Нельзя создать Диалог с самим собой.')
        u1, u2 = (user_a, user_b) if user_a.id < user_b.id else (user_b, user_a)
        chat = cls.objects.filter(user1=u1, user2=u2, publication=publication).first()
        if chat:
            return chat, False
        chat = cls.objects.create(user1=u1, user2=u2, publication=publication)
        return chat, True


class Message(models.Model):
    chat = models.ForeignKey(Chat,on_delete=models.CASCADE,related_name='messages',verbose_name='Диалог',)
    author = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='messages',verbose_name='Автор',)
    text = models.TextField('Текст')
    is_read = models.BooleanField('Прочитано', default=False)
    created_at = models.DateTimeField('Отправлено', auto_now_add=True)

    class Meta:
        verbose_name = 'Сообщение'
        verbose_name_plural = 'Сообщения'
        ordering = ['created_at']
        indexes = [models.Index(fields=['chat', 'created_at'])]

    def __str__(self):
        return f'{self.author}: {self.text[:30]}'