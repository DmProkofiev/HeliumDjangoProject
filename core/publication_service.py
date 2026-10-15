import os
import shutil
import uuid
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.template.defaultfilters import slugify

from core.models import Publication, Tag

ALLOWED = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024
MAX_IMAGES = 10

# READ
def get_active_publication(slug):
    return get_object_or_404(Publication, slug=slug, status='active')

def get_publication_for_edit(slug, user):
    pub = get_object_or_404(Publication, slug=slug)
    if pub.author_id != user.id:
        raise PermissionDenied('Это не ваша публикация')
    return pub

# CREATE
@transaction.atomic
def create_publication(form, user, files=None):
    pub = form.save(commit=False)
    pub.author = user
    pub.image = []
    pub.save()
    _save_tags(pub, form)
    if files:
        _append_images(pub, files)
    return pub

# UPDATE
@transaction.atomic
def update_publication(publication, form, files=None):
    obj = form.save(commit=False)
    obj.pk = publication.pk
    obj.save()
    _save_tags(obj, form)
    if files:
        _append_images(obj, files)
    return obj

# DELETE
@transaction.atomic
def delete_publication(publication):
    folder = _folder(publication)
    publication.delete()
    if os.path.isdir(folder):
        shutil.rmtree(folder, ignore_errors=True)

# DELETE
@transaction.atomic
def delete_publication_image(publication, index, user):
    if publication.author_id != user.id:
        raise PermissionDenied('Это не ваша публикация')
    names = list(publication.image_list)
    if index < 0 or index >= len(names):
        return
    name = os.path.basename(names.pop(index))   # защита от path traversal
    path = os.path.join(_folder(publication), name)
    if os.path.isfile(path):
        os.remove(path)
    publication.image = names
    publication.save(update_fields=['image'])


def _folder(publication):
    return os.path.join(str(settings.PUBLICATION_STORAGE_ROOT), f'PubItem_{publication.pk}')

def _append_images(publication, files):
    folder = _folder(publication)
    os.makedirs(folder, exist_ok=True)
    names = list(publication.image_list)
    if len(names) + len(files) > MAX_IMAGES:
        raise ValidationError(f'Максимум {MAX_IMAGES} изображений на публикацию')
    max_num = 0
    if os.path.isdir(folder):
        for f in os.listdir(folder):
            if not f.startswith('image_item_'):
                continue
            stem, _ = os.path.splitext(f)
            parts = stem.split('_')
            if len(parts) >= 4 and parts[-1].isdigit():
                max_num = max(max_num, int(parts[-1]))
    number = max_num + 1

    for file in files:
        if file.size > MAX_FILE_SIZE:
            raise ValidationError(
                f'Файл {file.name} больше {MAX_FILE_SIZE // (1024 * 1024)} МБ'
            )
        ext = os.path.splitext(os.path.basename(file.name))[1].lower()
        if ext not in ALLOWED:
            raise ValidationError(f'Недопустимый формат файла: {file.name}')

        fname = f'image_item_{publication.pk}_{number}_{uuid.uuid4().hex[:8]}{ext}'
        number += 1

        with open(os.path.join(folder, fname), 'wb+') as dest:
            for chunk in file.chunks():
                dest.write(chunk)

        names.append(fname)

    publication.image = names
    publication.save(update_fields=['image'])

def _save_tags(publication, form):
    raw = form.cleaned_data.get('tags_input', '') or ''
    names = [n.strip() for n in raw.split(',') if n.strip()]
    tags = []
    for name in names:
        base_slug = slugify(name) or 'tag'
        slug = base_slug
        existing = Tag.objects.filter(slug=slug).first()
        if existing and existing.name != name:
            i = 1
            while Tag.objects.filter(slug=slug).exists():
                slug = f'{base_slug}-{i}'
                i += 1
        tag, _ = Tag.objects.get_or_create(name=name, defaults={'slug': slug})
        tags.append(tag)
    publication.tags.set(tags)

@transaction.atomic
def set_main_image(publication, index, user):
    if publication.author_id != user.id:
        raise PermissionDenied('Это не ваша публикация')
    names = list(publication.image_list)
    if index <= 0 or index >= len(names):
        return
    name = names.pop(index)
    names.insert(0, name)
    publication.image = names
    publication.save(update_fields=['image'])