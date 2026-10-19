import logging

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q

from core import publication_service
from core.models import Publication
from .models import User
from .permissions import is_admin_user

logger = logging.getLogger(__name__)

# ВНУТРЕННИЕ
def _ensure_admin(actor):
    if not is_admin_user(actor):
        raise PermissionDenied('Доступ только для администратора')

# ПОЛЬЗОВАТЕЛИ
def list_users(query=None):
    qs = User.objects.all().order_by('-date_joined')
    if query:
        qs = qs.filter(
            Q(username__icontains=query)
            | Q(email__icontains=query)
            | Q(phone__icontains=query)
        )
    return qs


def toggle_user_block(actor, target_id):
    _ensure_admin(actor)

    target = User.objects.get(id=target_id)
    if target.id == actor.id:
        raise ValueError('Нельзя заблокировать собственный аккаунт')
    if target.is_superuser:
        raise ValueError('Нельзя заблокировать суперпользователя')

    target.is_active = not target.is_active
    target.save(update_fields=['is_active'])
    logger.info(
        'Admin %s %s user %s',
        actor.id,
        'blocked' if not target.is_active else 'unblocked',
        target.id,
    )
    return target

# ПУБЛИКАЦИИ
def list_publications(query=None, status=None):
    qs = (
        Publication.objects
        .select_related('author', 'category')
        .order_by('-created_at')
    )
    if query:
        qs = qs.filter(
            Q(title__icontains=query)
            | Q(author__username__icontains=query)
        )
    allowed_statuses = {'active', 'frozen', 'in_progress', 'closed', 'archived'}
    if status in allowed_statuses:
        qs = qs.filter(status=status)
    return qs

def freeze_publication(actor, slug):
    _ensure_admin(actor)
    publication = Publication.objects.get(slug=slug)
    if publication.status == 'frozen':
        return publication, False
    publication.status = 'frozen'
    publication.save(update_fields=['status', 'updated_at'])
    logger.info('Admin %s froze publication %s', actor.id, publication.id)
    return publication, True

def unfreeze_publication(actor, slug):
    _ensure_admin(actor)
    publication = Publication.objects.get(slug=slug)
    if publication.status != 'frozen':
        return publication, False

    publication.status = 'active'
    publication.save(update_fields=['status', 'updated_at'])
    logger.info('Admin %s unfroze publication %s', actor.id, publication.id)
    return publication, True

def delete_publication(actor, slug):
    _ensure_admin(actor)
    publication = Publication.objects.get(slug=slug)
    title = publication.title
    publication_id = publication.id
    publication_service.delete_publication(publication)
    logger.info('Admin %s deleted publication %s', actor.id, publication_id)
    return title

def get_publication_for_admin_edit(actor, slug):
    _ensure_admin(actor)
    return Publication.objects.get(slug=slug)

@transaction.atomic
def update_publication(actor, publication, form, files=None):
    _ensure_admin(actor)
    result = publication_service.update_publication(publication, form, files)
    logger.info('Admin %s updated publication %s', actor.id, publication.id)
    return result