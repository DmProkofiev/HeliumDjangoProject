from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render
from core.models import Publication, Category, Tag

def index_view(request):
    publication_type = request.GET.get('type', 'service')

    publications = Publication.objects.filter(publication_type=publication_type,status='active',).select_related('author', 'category').prefetch_related('tags')

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

    context = {
        'publications': page_obj,
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
        'publication_type': publication_type,
        'recommendations': recommendations,
    }
    return render(request, 'core/index.html', context)

def publication_detail_view(request):
    return render(request, 'core/index.html')

def publication_list_view(request):
    return render(request, 'core/index.html')