from django.core.paginator import Paginator
from django.db.models import Count, Q
from core.models import Publication
DEFAULT_PAGE_SIZE = 12

def publication_queryset():
    """
    Базовый набор активных публикаций с author/category/tags
    и аннотацией likes_count_annotated.
    """
    return (
        Publication.objects
        .filter(status='active')
        .select_related('author', 'category')
        .prefetch_related('tags')
        .annotate(likes_count_annotated=Count('favorited_by', distinct=True))
    )


def apply_filters(qs, *, query=None, category=None, tag=None,price_min=None, price_max=None, sort=None):
    """
    Применяет пользовательские фильтры к queryset публикаций.
    - query       — строка поиска (по title/description/category/tags)
    - category    — ID (int/str) или slug категории
    - tag         — ID (int/str) или slug тега
    - price_min   — минимальная цена
    - price_max   — максимальная цена
    - sort        — одно из разрешённых значений
    """
    if query:
        qs = qs.filter(
            Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(category__name__icontains=query)
            | Q(tags__name__icontains=query)
            | Q(author__username__icontains=query)
        ).distinct()

    if category:
        if str(category).isdigit():
            qs = qs.filter(category_id=int(category))
        else:
            qs = qs.filter(category__slug=category)

    if tag:
        if str(tag).isdigit():
            qs = qs.filter(tags__id=int(tag))
        else:
            qs = qs.filter(tags__slug=tag)

    if price_min:
        qs = qs.filter(price__gte=price_min)
    if price_max:
        qs = qs.filter(price__lte=price_max)

    allowed_sorts = {'-created_at', 'created_at', 'price', '-price', 'title', '-title'}
    if sort in allowed_sorts:
        qs = qs.order_by(sort)
    else:
        qs = qs.order_by('-created_at')

    return qs


def attach_user_flags(qs, user):
    """
    Возвращает множества ID публикаций, которые пользователь лайкнул
    и которые лежат у него в корзине.
    Используется в шаблонах для отрисовки активных состояний без N+1.
    """
    from accounts.models import Favorite, Cart

    if not user.is_authenticated:
        return set(), set()

    pub_ids = qs.values_list('id', flat=True)
    liked = set(Favorite.objects.filter(user=user, publication_id__in=pub_ids)
                .values_list('publication_id', flat=True))
    cart = set(Cart.objects.filter(user=user, publication_id__in=pub_ids)
               .values_list('publication_id', flat=True))
    return liked, cart


def paginate(qs, page_number, page_size=DEFAULT_PAGE_SIZE):
    """Оборачивает queryset в Paginator и возвращает текущую страницу."""
    paginator = Paginator(qs, page_size)
    return paginator.get_page(page_number), paginator


def build_category_sections():
    """
    Строит секции для главной ленты без N+1
    Один запрос, затем группировка в Python
    """
    from itertools import groupby
    from core.models import Category

    publications = list(
        Publication.objects
        .filter(status='active')
        .select_related('author', 'category')
        .prefetch_related('tags')
        .annotate(likes_count_annotated=Count('favorited_by', distinct=True))
        .order_by('category_id', '-created_at')
    )

    categories_by_id = {c.id: c for c in Category.objects.all()}

    sections = []
    for category_id, group in groupby(publications, key=lambda p: p.category_id):
        pubs = list(group)
        if category_id is None:
            sections.append({
                'category': None,
                'title': 'Разное',
                'publications': pubs,
            })
        else:
            sections.append({
                'category': categories_by_id.get(category_id),
                'publications': pubs,
            })
    return sections