from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import F
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST

from core import publication_service, search_service
from core.forms import PublicationForm
from core.models import Publication, Category, Tag
from core.selectors import (
    apply_filters,
    attach_user_flags,
    build_category_sections,
    paginate,
    publication_queryset,
)
from recommendations.logging_service import log_interaction
from recommendations.recommendation_service import get_recommendations

# ЛЕНТА
def feed_view(request):
    query = request.GET.get('q')
    category_id = request.GET.get('category')
    tag_id = request.GET.get('tag')
    price_min = request.GET.get('price_min')
    price_max = request.GET.get('price_max')
    sort = request.GET.get('sort', '-created_at')
    has_filters = any([query, category_id, tag_id, price_min, price_max, sort != '-created_at'])
    base_qs = publication_queryset()
    if has_filters:
        filtered = apply_filters(
            base_qs,
            query=query,
            category=category_id,
            tag=tag_id,
            price_min=price_min,
            price_max=price_max,
            sort=sort,
        )
        page_obj, paginator = paginate(filtered, request.GET.get('page'), page_size=12)
        liked_ids, cart_ids = attach_user_flags(filtered, request.user)
        sections = []
    else:
        page_obj = None
        paginator = None
        liked_ids, cart_ids = attach_user_flags(base_qs, request.user)
        sections = build_category_sections()

    recommendations = get_recommendations(request, limit=6)

    return render(request, 'core/feed.html', {
        'page_obj': page_obj,
        'recommendations': recommendations,
        'is_paginated': bool(page_obj and page_obj.has_other_pages()),
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
        'sections': sections,
        'has_filters': has_filters,
    })

# ДЕТАЛИ ПУБЛИКАЦИИ
def publication_detail_view(request, slug):
    """
    Страница публикации.
    Инкремент просмотров — атомарный UPDATE без refresh_from_db,
    чтобы не терять аннотацию likes_count_annotated
    """
    publication = get_object_or_404(publication_queryset(),slug=slug)
    Publication.objects.filter(pk=publication.pk).update(views=F('views') + 1)
    publication.views += 1

    try:
        log_interaction(request, 'view', publication=publication)
    except Exception:
        pass

    liked_ids, cart_ids = attach_user_flags(
        Publication.objects.filter(pk=publication.pk),
        request.user,
    )
    recommendations = get_recommendations(request, limit=4)

    return render(request, 'core/publication_detail.html', {
        'publication': publication,
        'liked_ids': liked_ids,
        'cart_ids': cart_ids,
        'recommendations': recommendations,
    })

# ПОИСК
def search_view(request):
    """
    Отдельная страница поиска с фильтрами.
    Релевантность и пагинация — в search_service
    """
    query = request.GET.get('q', '')
    result = search_service.search_publications(
        query=query,
        category=request.GET.get('category'),
        tag=request.GET.get('tag'),
        price_min=request.GET.get('price_min'),
        price_max=request.GET.get('price_max'),
        sort=request.GET.get('sort'),
        page=request.GET.get('page', 1),
    )
    try:
        log_interaction(request, 'search', search_query=query)
    except Exception:
        pass

    liked_ids, cart_ids = attach_user_flags(result['page_obj'].object_list, request.user)

    return render(request, 'core/search_results.html', {
        **result,
        'categories': Category.objects.all(),
        'tags': Tag.objects.all(),
        'liked_ids': liked_ids,
        'cart_ids': cart_ids,
    })


# ПУБЛИКАЦИИ ОДНОЙ КАТЕГОРИИ
def publication_list_view(request):
    """
    Публикации выбранной категории с сортировкой и пагинацией
    """
    category_val = request.GET.get('category')
    category = None

    qs = apply_filters(publication_queryset(), category=category_val)

    if category_val:
        if str(category_val).isdigit():
            category = Category.objects.filter(id=int(category_val)).first()
        else:
            category = Category.objects.filter(slug=category_val).first()

    sort = request.GET.get('sort', 'new')
    if sort == 'price_asc':
        qs = qs.order_by('price')
    elif sort == 'price_desc':
        qs = qs.order_by('-price')
    else:
        qs = qs.order_by('-created_at')

    page_obj, _ = paginate(qs, request.GET.get('page'), page_size=24)
    liked_ids, cart_ids = attach_user_flags(qs, request.user)

    return render(request, 'core/publication_list.html', {
        'category': category,
        'page_obj': page_obj,
        'sort': sort,
        'liked_ids': liked_ids,
        'cart_ids': cart_ids,
        'is_paginated': page_obj.has_other_pages(),
    })


# CRUD ПУБЛИКАЦИИ
@login_required
def publication_create_view(request):
    """Создание публикации"""
    if request.method == 'POST':
        form = PublicationForm(request.POST, request.FILES)
        files = request.FILES.getlist('images_upload')
        if form.is_valid():
            publication_service.create_publication(form, request.user, files)
            messages.success(request, 'Публикация создана')
            return redirect('/accounts/profile/?tab=publications')
    else:
        form = PublicationForm()

    return render(request, 'core/publication_form.html', {
        'form': form,
        'is_edit': False,
    })

@login_required
def publication_update_view(request, slug):
    """Редактирование своей публикации"""
    publication = publication_service.get_publication_for_edit(slug, request.user)

    if request.method == 'POST':
        form = PublicationForm(request.POST, request.FILES, instance=publication)
        files = request.FILES.getlist('images_upload')
        if form.is_valid():
            publication_service.update_publication(publication, form, files)
            messages.success(request, 'Изменения сохранены')
            return redirect('/accounts/profile/?tab=publications')
    else:
        form = PublicationForm(instance=publication)

    return render(request, 'core/publication_form.html', {
        'form': form,
        'publication': publication,
        'is_edit': True,
    })

@login_required
@require_POST
def publication_remove_view(request, slug):
    """Удаление своей публикации."""
    publication = publication_service.get_publication_for_edit(slug, request.user)
    publication_service.delete_publication(publication)
    messages.success(request, 'Публикация удалена')
    return redirect('/accounts/profile/?tab=publications')

@login_required
@require_POST
def publication_image_remove_view(request, slug, index):
    """Удаление отдельного изображения публикации"""
    publication = publication_service.get_publication_for_edit(slug, request.user)
    publication_service.delete_publication_image(publication, index, request.user)
    messages.success(request, 'Фото удалено')
    return redirect('core:publication_update', slug=slug)

@login_required
@require_POST
def publication_image_set_main_view(request, slug, index):
    """Назначение изображения основным"""
    publication = publication_service.get_publication_for_edit(slug, request.user)
    publication_service.set_main_image(publication, index, request.user)
    messages.success(request, 'Основное фото обновлено')
    return redirect('core:publication_update', slug=slug)