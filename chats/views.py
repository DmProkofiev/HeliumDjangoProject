from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from accounts.models import User
from core.models import Publication
from .models import Chat, Message

# READ
@login_required
def chat_list_view(request):
    chats = Chat.objects.filter(Q(user1=request.user) | Q(user2=request.user)).select_related('user1', 'user2', 'publication').order_by('-updated_at')
    chats_data = [
        {
            'chat': chat,
            'other': chat.get_other_user(request.user),
            'last_message': chat.last_message(),
            'unread': chat.unread_count_for(request.user),
        }
        for chat in chats
    ]
    return render(request, 'chats/chat_list.html', {'chats_data': chats_data})


@login_required
def chat_detail_view(request, chat_id):
    chat = get_object_or_404(Chat, id=chat_id)
    if not chat.has_participant(request.user):
        raise PermissionDenied('Вы не являетесь участником этого чата')
    chat.messages.filter(is_read=False).exclude(author=request.user).update(is_read=True)
    return render(request, 'chats/chat_detail.html', {
        'chat': chat,
        'chat_messages': chat.messages.select_related('author'),
        'other_user': chat.get_other_user(request.user)
    })

# CREATE
@login_required
@require_POST
def create_chat_from_publication_view(request, publication_id):
    publication = get_object_or_404(Publication, id=publication_id)
    if publication.author_id == request.user.id:
        return redirect('core:publication_detail', slug=publication.slug)
    chat, _ = Chat.get_or_create_between(user_a=request.user, user_b=publication.author, publication=publication)
    return redirect('chats:chat_detail', chat_id=chat.id)

@login_required
@require_POST
def create_free_chat_view(request, user_id):
    other = get_object_or_404(User, id=user_id)
    if other.id == request.user.id:
        return redirect('accounts:profile')
    chat, _ = Chat.get_or_create_between(request.user, other)
    return redirect('chats:chat_detail', chat_id=chat.id)

# UPDATE
@login_required
@require_POST
def update_message_view(request, message_id):
    message = get_object_or_404(Message, id=message_id)
    if message.author_id != request.user.id:
        raise PermissionDenied('Нельзя редактировать чужое сообщение.')
    if not message.chat.has_participant(request.user):
        raise PermissionDenied('Вы не участник этого чата')
    text = request.POST.get('text', '').strip()
    if text and len(text) <= 2000:
        message.text = text
        message.save(update_fields=['text'])
    return redirect('chats:chat_detail', chat_id=message.chat_id)

# DELETE
@login_required
@require_POST
def remove_message_view(request, message_id):
    message = get_object_or_404(Message, id=message_id)
    if message.author_id != request.user.id:
        raise PermissionDenied('Нельзя удалить чужое сообщение')
    chat_id = message.chat_id
    message.delete()
    return redirect('chats:chat_detail', chat_id=chat_id)

@login_required
@require_POST
def remove_chat_view(request, chat_id):
    chat = get_object_or_404(Chat, id=chat_id)
    if not chat.has_participant(request.user):
        raise PermissionDenied('Вы не участник этого диалога')
    chat.delete()
    return redirect('chats:list')