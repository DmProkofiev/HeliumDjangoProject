from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from accounts.models import Favorite, Cart
from core import publication_service
from core.forms import PublicationForm
from core.models import Publication, Category, Tag

# Лента
def feed_view(request):
    publication_type = request.GET.get('type', 'service')
    publications = (Publication.objects.filter(status='active').select_related('author', 'category').prefetch_related('tags').annotate(likes_count=Count('favorited_by', distinct=True)))
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

    liked_ids = set()
    cart_ids = set()
    if request.user.is_authenticated:
        liked_ids = set(Favorite.objects.filter(user=request.user).values_list('publication_id', flat=True))
        cart_ids = set(Cart.objects.filter(user=request.user).values_list('publication_id', flat=True))
    has_filters = any([query, category_id, tag_id, price_min, price_max])

    sections = []
    if not has_filters:
        categories_with_pubs = Category.objects.annotate(pubs_count=Count('publications', filter=Q(publications__status='active'))).filter(pubs_count__gt=0).order_by('name')

        base_qs = (Publication.objects.filter(status='active').select_related('author', 'category').prefetch_related('tags').annotate(likes_count_annotated=Count('favorited_by', distinct=True)))

        for category in categories_with_pubs:
            pubs = list(base_qs.filter(category=category).order_by('-created_at'))
            if pubs:
                sections.append({'category': category, 'publications': pubs})

        no_category_pubs = list(base_qs.filter(category__isnull=True).order_by('-created_at'))
        if no_category_pubs:
            sections.append({
                'category': None,
                'title': 'Разное',
                'publications': no_category_pubs,
            })

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
        'sections': sections,
        'has_filters': has_filters,
    })

def publication_detail_view(request, slug):
    publication = get_object_or_404(
        Publication.objects
        .select_related('author', 'category')
        .prefetch_related('tags')
        .annotate(likes_count_annotated=Count('favorited_by', distinct=True)),
        slug=slug,
        status='active',
    )
    liked_ids = set()
    cart_ids = set()
    if request.user.is_authenticated:
        from accounts.models import Favorite, Cart
        liked_ids = set(Favorite.objects.filter(user=request.user).values_list('publication_id', flat=True))
        cart_ids = set(Cart.objects.filter(user=request.user).values_list('publication_id', flat=True))
    return render(request, 'core/publication_detail.html', {'publication': publication,'liked_ids': liked_ids,'cart_ids': cart_ids})

def publication_list_view(request):
    category_id = request.GET.get('category')
    category = None
    publications = (
        Publication.objects
        .select_related('author', 'category')
        .annotate(likes_count_annotated=Count('favorited_by', distinct=True))
    )
    if category_id:
        category = get_object_or_404(Category, id=category_id)
        publications = publications.filter(category=category)
    # Сортировка
    sort = request.GET.get('sort', 'new')
    if sort == 'price_asc':
        publications = publications.order_by('price')
    elif sort == 'price_desc':
        publications = publications.order_by('-price')
    else:
        publications = publications.order_by('-created_at')
    paginator = Paginator(publications, 24)
    page_obj = paginator.get_page(request.GET.get('page'))
    liked_ids, cart_ids = set(), set()
    if request.user.is_authenticated:
        liked_ids = set(
            Favorite.objects.filter(user=request.user)
            .values_list('publication_id', flat=True)
        )
        cart_ids = set(
            Cart.objects.filter(user=request.user)
            .values_list('publication_id', flat=True)
        )
    context = {
        'category': category,
        'page_obj': page_obj,
        'publications': page_obj.object_list,
        'sort': sort,
        'liked_ids': liked_ids,
        'cart_ids': cart_ids,
        'is_paginated': page_obj.has_other_pages(),
    }
    return render(request, 'core/publication_list.html', context)

# CRUD publication
@login_required
def publication_create_view(request):
    if request.method == 'POST':
        form = PublicationForm(request.POST, request.FILES)
        files = request.FILES.getlist('images_upload')   # ← все файлы

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
    publication = publication_service.get_publication_for_edit(slug, request.user)
    publication_service.delete_publication(publication)
    messages.success(request, 'Публикация удалена')
    return redirect('/accounts/profile/?tab=publications')

@login_required
@require_POST
def publication_image_remove_view(request, slug, index):
    publication = publication_service.get_publication_for_edit(slug, request.user)
    publication_service.delete_publication_image(publication, index, request.user)
    messages.success(request, 'Фото удалено')
    return redirect('core:publication_update', slug=slug)

@login_required
@require_POST
def publication_image_set_main_view(request, slug, index):
    publication = publication_service.get_publication_for_edit(slug, request.user)
    publication_service.set_main_image(publication, index, request.user)
    messages.success(request, 'Основное фото обновлено')
    return redirect('core:publication_update', slug=slug)