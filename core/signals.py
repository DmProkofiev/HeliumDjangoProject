from django.core.cache import cache
from django.db.models import F
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from accounts.models import Favorite
from .models import Category

@receiver([post_save, post_delete], sender=Category)
def clear_categories_cache(sender, **kwargs):
    cache.delete('menu_categories')

@receiver(post_save, sender=Favorite)
def like_created(sender, instance, created, **kwargs):
    if created:
        instance.publication.__class__.objects.filter(pk=instance.publication_id).update(likes=F('likes') + 1)

@receiver(post_delete, sender=Favorite)
def like_deleted(sender, instance, **kwargs):
    instance.publication.__class__.objects.filter(pk=instance.publication_id, likes__gt=0,).update(likes=F('likes') - 1)