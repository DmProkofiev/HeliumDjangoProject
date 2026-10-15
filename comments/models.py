from django.conf import settings
from django.db import models
from core.models import Publication

class Comments(models.Model):
    publication = models.ForeignKey(Publication, on_delete=models.CASCADE, related_name='comments', verbose_name='Объявление')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='comments', verbose_name='Автор')
    text = models.TextField('Текст комментария')
    image = models.JSONField('Имена изображений', default=list, blank=True)
    created_at = models.DateTimeField('Создано', auto_now_add=True)

    class Meta:
        verbose_name = 'Комментарий'
        verbose_name_plural = 'Комментарии'
        ordering = ['created_at']

    def __str__(self):
        return f'Комментарий от {self.author.username}'

    @property
    def image_list(self):
        v = self.image
        if isinstance(v, list):
            return [str(x) for x in v if x]
        if isinstance(v, str) and v:
            return [v]
        return []

    @property
    def image_urls(self):
        from urllib.parse import quote
        base = getattr(settings, 'PUBLICATION_STORAGE_URL', '/publication-files/').rstrip('/')
        prefix = (
            f'{base}/PubItem_{self.publication_id}'
            f'/Comments/ItemOfComment_{self.pk}' )
        return [f'{prefix}/{quote(n)}' for n in self.image_list]