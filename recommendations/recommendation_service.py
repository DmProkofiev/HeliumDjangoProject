import hashlib
import logging
import re

from django.core.cache import cache
from django.db.models import Count, Max
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

from core.models import Publication
from .models import UserInteraction

logger = logging.getLogger(__name__)
MATRIX_CACHE_TTL = 60 * 15          # 15 минут
RECOMMENDATION_CACHE_TTL = 60 * 5   # 5 минут
MAX_INTERACTIONS = 10


def _matrix_cache_key():
    """
    Строит ключ инвалидации матрицы: меняется, когда меняется набор
    активных публикаций (по количеству / максимальному id / свежести).
    """
    stats = Publication.objects.filter(status='active').aggregate(
        n=Count('id'),
        max_pk=Max('id'),
        last=Max('updated_at'),
    )
    raw = f"{stats['n']}|{stats['max_pk']}|{stats['last']}"
    return 'reco:matrix:' + hashlib.md5(raw.encode()).hexdigest()


def _get_vectorizer_and_matrix():
    """
    Возвращает (publications, tfidf_matrix) для активных публикаций
    Матрица кешируется; пересчитывается только при изменении публикаций
    """
    key = _matrix_cache_key()
    cached = cache.get(key)
    if cached is not None:
        return cached

    pubs = list(
        Publication.objects
        .filter(status='active')
        .prefetch_related('tags', 'category')
    )
    if not pubs:
        return None

    corpus = []
    for pub in pubs:
        tags = " ".join(t.name for t in pub.tags.all())
        category = pub.category.name if pub.category else ""
        text = f"{pub.title} {pub.title} {category} {category} {tags} {pub.description}"
        corpus.append(re.sub(r'[^\w\s]', '', text.lower()))

    vectorizer = TfidfVectorizer()
    matrix = vectorizer.fit_transform(corpus)

    cache.set(key, (pubs, matrix), MATRIX_CACHE_TTL)
    return pubs, matrix

def _user_cache_key(user, session_key, limit):
    """Ключ кеша рекомендаций для конкретного пользователя или сессии."""
    identity = f"u{user.id}" if user else f"s{session_key}"
    return f'reco:{identity}:{limit}'


def get_recommendations(request, limit=6):
    """
    Возвращает список рекомендованных публикаций.
    - Аноним без сессии  -> популярные.
    - Нет истории        -> популярные.
    - Иначе              -> TF-IDF-похожесть по лайкам/просмотрам/корзине.
    Кешируется на 5 минут.
    """
    user = request.user if request.user.is_authenticated else None
    session_key = request.session.session_key if not user else None

    if not user and not session_key:
        return _get_popular_publications(limit)

    cache_key = _user_cache_key(user, session_key, limit)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    interaction_qs = (
        UserInteraction.objects
        .filter(
            user=user,
            session_key=session_key,
            action_type__in=['like', 'view', 'cart'],
            publication__isnull=False,
        )
        .values_list('publication_id', flat=True)
        .distinct()[:MAX_INTERACTIONS]
    )
    interaction_ids = list(interaction_qs)

    if not interaction_ids:
        result = _get_popular_publications(limit)
        cache.set(cache_key, result, RECOMMENDATION_CACHE_TTL)
        return result

    built = _get_vectorizer_and_matrix()
    if not built:
        return _get_popular_publications(limit)

    pubs, matrix = built
    idx_by_id = {pub.id: i for i, pub in enumerate(pubs)}
    target_idx = [idx_by_id[pid] for pid in interaction_ids if pid in idx_by_id]
    if not target_idx:
        result = _get_popular_publications(limit)
        cache.set(cache_key, result, RECOMMENDATION_CACHE_TTL)
        return result
    cosine_similarities = linear_kernel(matrix[target_idx], matrix).mean(axis=0)
    related_indices = cosine_similarities.argsort()[::-1]
    recommendations = []
    for i in related_indices:
        pub = pubs[i]
        if pub.id not in interaction_ids:
            recommendations.append(pub)
            if len(recommendations) >= limit:
                break
    cache.set(cache_key, recommendations, RECOMMENDATION_CACHE_TTL)
    return recommendations

def _get_popular_publications(limit):
    """Топ публикаций по лайкам — фолбэк для холодного старта"""
    return list(
        Publication.objects.filter(status='active')
        .annotate(total_likes=Count('favorited_by'))
        .order_by('-total_likes', '-created_at')[:limit]
    )