from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Category

@receiver([post_save, post_delete], sender=Category)
def clear_categories_cache(sender, **kwargs):
    cache.delete('menu_categories')