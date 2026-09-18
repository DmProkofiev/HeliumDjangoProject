from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from accounts.models import User
from core.models import Publication
from .models import Chat, Message

@login_required
def chat_list(request):
    chats = Chat.objects.filter(Q(user1=request.user) | Q(user2=request.user)).select_related('user1', 'user2', 'publication').order_by('-updated_at')
    chats_data = []
    for chat in chats:
        chats_data.append({
            'chat': chat,
            'other': chat.get_other_user(request.user),
            'last_message': chat.last_message(),
            'unread': chat.unread_count_for(request.user),
        })
    return render(request, 'chats/list.html', {'chats_data': chats_data})

@login_required
def chat_detail(request, chat_id):
    chat = get_object_or_404(Chat, id=chat_id)
    if not chat.has_participant(request.user):
        return render(request, 'chats/forbidden.html', status=403)
    chat.messages.filter(is_read=False).exclude(author=request.user).update(is_read=True)
    messages = chat.messages.select_related('author')
    other_user = chat.get_other_user(request.user)
    return render(request, 'chats/detail.html', {'chat': chat,'messages': messages,'other_user': other_user,})

@login_required
def start_chat_from_publication(request, publication_id):
    publication = get_object_or_404(Publication, id=publication_id)
    if publication.author_id == request.user.id:
        return redirect('core:publication_detail', slug=publication.slug)
    chat, _ = Chat.get_or_create_between(user_a=request.user,user_b=publication.author,publication=publication,)
    return redirect('chats:detail', chat_id=chat.id)

@login_required
def start_free_chat(request, user_id):
    other = get_object_or_404(User, id=user_id)
    if other.id == request.user.id:
        return redirect('accounts:profile')
    chat, _ = Chat.get_or_create_between(request.user, other)
    return redirect('chats:detail', chat_id=chat.id)