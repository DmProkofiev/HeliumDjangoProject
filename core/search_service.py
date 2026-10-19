import logging

from django.contrib.postgres.search import TrigramSimilarity
from django.core.paginator import Paginator
from django.db import connection
from django.db.models import Case, Count, IntegerField, Max, Q, Value, When
from core.models import Publication
logger = logging.getLogger(__name__)
DEFAULT_PAGE_SIZE = 12
MIN_QUERY_LENGTH = 2
MAX_QUERY_LENGTH = 200
ALLOWED_SORTS = {'price', '-price', 'title', '-title', 'created_at', '-created_at'}
_TRIGRAM_AVAILABLE = None

def _has_trigram_extension():
    """
    Проверяет, установлено ли расширение pg_trgm.
    Результат кешируется на время жизни процесса.
    """
    global _TRIGRAM_AVAILABLE
    if _TRIGRAM_AVAILABLE is not None:
        return _TRIGRAM_AVAILABLE
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'")
            _TRIGRAM_AVAILABLE = cursor.fetchone() is not None
    except Exception:
        _TRIGRAM_AVAILABLE = False
    return _TRIGRAM_AVAILABLE


def _resolve_category_qs(qs, value):
    """Применяет фильтр по категории (id или slug)"""
    if not value:
        return qs
    if str(value).isdigit():
        return qs.filter(category_id=int(value))
    return qs.filter(category__slug=value)


def _resolve_tag_qs(qs, value):
    """Применяет фильтр по тегу (id или slug)"""
    if not value:
        return qs
    if str(value).isdigit():
        return qs.filter(tags__id=int(value))
    return qs.filter(tags__slug=value)


def search_publications(query, *, category=None, tag=None,price_min=None, price_max=None,sort=None, page=1):
    """
    Основная функция поиска публикаций
    Возвращает словарь с контекстом для шаблона
    """
    qs = (
        Publication.objects
        .filter(status='active')
        .select_related('author', 'category')
        .prefetch_related('tags')
        .annotate(likes_count_annotated=Count('favorited_by', distinct=True))
    )
    q = (query or '').strip()[:MAX_QUERY_LENGTH]
    has_query = len(q) >= MIN_QUERY_LENGTH
    if has_query:
        if _has_trigram_extension():
            qs = qs.annotate(
                _sim_title=TrigramSimilarity('title', q),
                _sim_desc=TrigramSimilarity('description', q),
            ).filter(
                Q(_sim_title__gt=0.1)
                | Q(_sim_desc__gt=0.1)
                | Q(title__icontains=q)
                | Q(tags__name__icontains=q)
            ).distinct()
        else:
            qs = qs.filter(
                Q(title__icontains=q)
                | Q(description__icontains=q)
                | Q(tags__name__icontains=q)
            ).distinct()
        qs = qs.annotate(
            _relevance=Max(
                Case(
                    When(title__icontains=q, then=Value(3)),
                    When(tags__name__icontains=q, then=Value(2)),
                    When(description__icontains=q, then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            )
        )

    qs = _resolve_category_qs(qs, category).distinct()
    qs = _resolve_tag_qs(qs, tag).distinct()

    if price_min:
        qs = qs.filter(price__gte=price_min)
    if price_max:
        qs = qs.filter(price__lte=price_max)

    if sort in ALLOWED_SORTS:
        qs = qs.order_by(sort)
    elif has_query:
        qs = qs.order_by('-_relevance', '-created_at')
    else:
        qs = qs.order_by('-created_at')

    paginator = Paginator(qs, DEFAULT_PAGE_SIZE)
    page_obj = paginator.get_page(page)

    return {
        'page_obj': page_obj,
        'total': paginator.count,
        'query': q,
        'has_query': has_query,
        'selected_category': category or '',
        'selected_tag': tag or '',
        'selected_sort': sort or '',
        'price_min': price_min or '',
        'price_max': price_max or '',
        'is_paginated': page_obj.has_other_pages(),
    }