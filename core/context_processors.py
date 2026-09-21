from django.core.cache import cache
from .models import Category

def categories(request):
    """
    Добавляет список категорий во все шаблоны.
    Кэшируется на 10 минут, чтобы не бить по БД на каждый запрос.
    """
    cats = cache.get('menu_categories')
    if cats is None:
        cats = list(Category.objects.all())
        cache.set('menu_categories', cats, 60 * 10)
    return {'menu_categories': cats}