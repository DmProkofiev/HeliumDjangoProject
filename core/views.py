from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from accounts.models import Favorite, Cart
from core.models import Publication, Category, Tag

def feed_view(request):
    publication_type = request.GET.get('type', 'service')
    publications = Publication.objects.filter(status='active').select_related('author', 'category').prefetch_related('tags')
    # Поиск
    query = request.GET.get('q')
    if query:
        publications = publications.filter(Q(title__icontains=query) | Q(description__icontains=query) | Q(category__name__icontains=query) | Q(tags__name__icontains=query) | Q(author__username__icontains=query)).distinct()
    # Фильтр по категории
    category_id = request.GET.get('category')
    if category_id:
        publications = publications.filter(category_id=category_id)
    # Фильтр по тегу
    tag_id = request.GET.get('tag')
    if tag_id:
        publications = publications.filter(tags__id=tag_id)
    # Фильтр по цене
    price_min = request.GET.get('price_min')
    price_max = request.GET.get('price_max')
    if price_min:
        publications = publications.filter(price__gte=price_min)
    if price_max:
        publications = publications.filter(price__lte=price_max)
    # Сортировка
    sort = request.GET.get('sort', '-created_at')
    allowed_sorts = {'-created_at', 'created_at', 'price', '-price', 'title', '-title'}
    if sort in allowed_sorts:
        publications = publications.order_by(sort)
    # Пагинация
    paginator = Paginator(publications, 12)
    page_obj = paginator.get_page(request.GET.get('page'))

    # Рекомендации (недоделано)
    recommendations = []
    if request.user.is_authenticated:
        try:
            from recommendations.services import get_recommendations_for_user
            recommendations = get_recommendations_for_user(request.user, limit=6)
        except ImportError:
            pass
    liked_ids = set()
    cart_ids = set()
    if request.user.is_authenticated:
        liked_ids = set(
            Favorite.objects.filter(user=request.user).values_list('publication_id', flat=True)
        )
        cart_ids = set(
            Cart.objects.filter(user=request.user).values_list('publication_id', flat=True)
        )
    return render(request, 'core/feed.html', {
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'categories': Category.objects.all(),
        'tags': Tag.objects.all(),
        'query': query,
        'selected_category': category_id,
        'selected_tag': tag_id,
        'selected_sort': sort,
        'price_min': price_min,
        'price_max': price_max,
        'liked_ids': liked_ids,
        'cart_ids': cart_ids,
    })

def publication_detail_view(request, slug):
    publication = get_object_or_404(Publication.objects.select_related('author', 'category').prefetch_related('tags'),slug=slug, status='active')
    liked_ids = set()
    cart_ids = set()
    if request.user.is_authenticated:
        from accounts.models import Favorite, Cart
        liked_ids = set(Favorite.objects.filter(user=request.user).values_list('publication_id', flat=True))
        cart_ids = set(Cart.objects.filter(user=request.user).values_list('publication_id', flat=True))
    return render(request, 'core/publication_detail.html', {'publication': publication,'liked_ids': liked_ids,'cart_ids': cart_ids})

def publication_list_view(request):
    return render(request, 'core/feed.html')

