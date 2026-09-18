import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.db.models import Q
from django.utils import timezone
from .models import Chat, Message

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        self.chat_id = self.scope['url_route']['kwargs']['chat_id']
        self.room_group_name = f'chat_{self.chat_id}'
        if not self.user.is_authenticated:
            await self.close()
            return
        if not await self.is_participant():
            await self.close()
            return
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return
        text = (data.get('text') or '').strip()
        if not text:
            return
        message = await self.save_message(text)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message_id': message['id'],
                'text': message['text'],
                'author_id': message['author_id'],
                'author': message['author'],
                'created_at': message['created_at'],
            }
        )
    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'message_id': event['message_id'],
            'text': event['text'],
            'author_id': event['author_id'],
            'author': event['author'],
            'created_at': event['created_at'],
        }))

    @database_sync_to_async
    def is_participant(self):
        return Chat.objects.filter(id=self.chat_id).filter(
            Q(user1=self.user) | Q(user2=self.user)
        ).exists()

    @database_sync_to_async
    def save_message(self, text):
        chat = Chat.objects.get(id=self.chat_id)
        message = Message.objects.create(chat=chat, author=self.user, text=text)
        chat.save(update_fields=['updated_at'])
        return {
            'id': message.id,
            'text': message.text,
            'author_id': message.author_id,
            'author': message.author.username,
            'created_at': message.created_at.isoformat(),
        }