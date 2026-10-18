from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel
from django.db.models import Count
from core.models import Publication
from .models import UserInteraction
import re

def get_recommendations(request, limit=6):
    user = request.user if request.user.is_authenticated else None
    session_key = request.session.session_key if not user else None
    if not user and not session_key:
        return _get_popular_publications(limit)
    interactions = UserInteraction.objects.filter(
        user=user,
        session_key=session_key,
        action_type__in=['like', 'view', 'cart'],
        publication__isnull=False
    ).values_list('publication_id', flat=True).distinct()[:10]
    if not interactions:
        return _get_popular_publications(limit)
    all_pubs = list(Publication.objects.filter(status='active').prefetch_related('tags', 'category'))
    corpus = []
    for pub in all_pubs:
        tags = " ".join([t.name for t in pub.tags.all()])
        category = pub.category.name if pub.category else ""
        text = f"{pub.title} {pub.title} {category} {category} {tags} {pub.description}"
        text = re.sub(r'[^\w\s]', '', text.lower())
        corpus.append(text)
    tfidf = TfidfVectorizer()
    tfidf_matrix = tfidf.fit_transform(corpus)
    target_indices = [i for i, pub in enumerate(all_pubs) if pub.id in interactions]
    if not target_indices:
        return _get_popular_publications(limit)
    cosine_similarities = linear_kernel(tfidf_matrix[target_indices], tfidf_matrix).mean(axis=0)
    related_indices = cosine_similarities.argsort()[::-1]
    recommendations = []
    for i in related_indices:
        pub = all_pubs[i]
        if pub.id not in interactions:
            recommendations.append(pub)
            if len(recommendations) >= limit:
                break

    return recommendations

def _get_popular_publications(limit):
    return list(
        Publication.objects.filter(status='active')
        .annotate(total_likes=Count('favorited_by'))
        .order_by('-total_likes', '-created_at')[:limit]
    )