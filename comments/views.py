from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from core.models import Publication
from .forms import CommentForm
from .models import Comments
from . import comment_service

@login_required
@require_POST
def comment_create_view(request, slug):
    publication = get_object_or_404(Publication, slug=slug, status='active')
    form = CommentForm(request.POST)

    if form.is_valid():
        files = request.FILES.getlist('images_upload')
        comment_service.create_comment(form, request.user, publication, files)
        messages.success(request, 'Комментарий добавлен')
    else:
        messages.error(request, 'Комментарий не может быть пустым')
    return redirect(publication.get_absolute_url())

@login_required
@require_POST
def comment_update_view(request, pk):
    comment = get_object_or_404(Comments, pk=pk)
    text = (request.POST.get('text') or '').strip()
    if not text:
        messages.error(request, 'Текст не может быть пустым')
        return redirect(comment.publication.get_absolute_url())

    files = request.FILES.getlist('images_upload')
    comment_service.update_comment(comment, request.user, text, files)
    messages.success(request, 'Комментарий обновлён')
    return redirect(comment.publication.get_absolute_url())

@login_required
@require_POST
def comment_delete_view(request, pk):
    comment = get_object_or_404(Comments, pk=pk)
    publication_url = comment.publication.get_absolute_url()
    comment_service.delete_comment(comment, request.user)
    messages.success(request, 'Комментарий удалён')
    return redirect(publication_url)

@login_required
@require_POST
def comment_image_remove_view(request, pk, index):
    comment = get_object_or_404(Comments, pk=pk)
    comment_service.delete_comment_image(comment, index, request.user)
    messages.success(request, 'Фото удалено')
    return redirect(comment.publication.get_absolute_url())