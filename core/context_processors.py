from django.core.cache import cache
from .models import Category

def categories(request):
    cats = cache.get('menu_categories')
    if cats is None:
        cats = list(Category.objects.all())
        cache.set('menu_categories', cats, 60 * 10)
    return {'menu_categories': cats}