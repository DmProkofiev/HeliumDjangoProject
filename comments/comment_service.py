import os
import shutil
import uuid
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from .models import Comments

ALLOWED = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024
MAX_IMAGES = 5


# ============================================================
# CREATE
# ============================================================
@transaction.atomic
def create_comment(form, user, publication, files=None):
    comment = form.save(commit=False)
    comment.author = user
    comment.publication = publication
    comment.image = []
    comment.save()

    if files:
        _append_images(comment, files)
    return comment


# ============================================================
# UPDATE
# ============================================================
@transaction.atomic
def update_comment(comment, user, text, files=None):
    if comment.author_id != user.id:
        raise PermissionDenied('Это не ваш комментарий')

    comment.text = text
    comment.save(update_fields=['text'])

    if files:
        _append_images(comment, files)
    return comment


# ============================================================
# DELETE
# ============================================================
@transaction.atomic
def delete_comment(comment, user):
    if comment.author_id != user.id:
        raise PermissionDenied('Это не ваш комментарий')

    folder = _folder(comment)
    comment.delete()
    if os.path.isdir(folder):
        shutil.rmtree(folder, ignore_errors=True)


# ============================================================
# DELETE IMAGE
# ============================================================
@transaction.atomic
def delete_comment_image(comment, index, user):
    if comment.author_id != user.id:
        raise PermissionDenied('Это не ваш комментарий')

    names = list(comment.image_list)
    if index < 0 or index >= len(names):
        return

    name = os.path.basename(names.pop(index))
    path = os.path.join(_folder(comment), name)
    if os.path.isfile(path):
        os.remove(path)

    comment.image = names
    comment.save(update_fields=['image'])


# ============================================================
# ВНУТРЕННИЕ
# ============================================================
def _folder(comment):
    """
    PublicationStorage/PubItem_<pub_id>/Comments/ItemOfComment_<comment_id>/
    """
    root = str(settings.PUBLICATION_STORAGE_ROOT)
    return os.path.join(
        root,
        f'PubItem_{comment.publication_id}',
        'Comments',
        f'ItemOfComment_{comment.pk}',
    )

def _append_images(comment, files):
    folder = _folder(comment)
    os.makedirs(folder, exist_ok=True)
    names = list(comment.image_list)
    if len(names) + len(files) > MAX_IMAGES:
        raise ValidationError(f'Максимум {MAX_IMAGES} изображений на комментарий')
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
        fname = f'image_item_{comment.pk}_{number}_{uuid.uuid4().hex[:8]}{ext}'
        number += 1
        with open(os.path.join(folder, fname), 'wb+') as dest:
            for chunk in file.chunks():
                dest.write(chunk)
        names.append(fname)
    comment.image = names
    comment.save(update_fields=['image'])