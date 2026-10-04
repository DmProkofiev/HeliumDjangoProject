from django.urls import path
from . import views

app_name = 'chats'

urlpatterns = [
    path('', views.chat_list_view, name='list'),
    path('<int:chat_id>/', views.chat_detail_view, name='chat_detail'),
    path('create/publication/<int:publication_id>/', views.create_chat_from_publication_view, name='start_from_publication'),
    path('create/user/<int:user_id>/', views.create_free_chat_view, name='start_free_chat'),
    path('message/<int:message_id>/edit/', views.update_message_view, name='update_message'),
    path('message/<int:message_id>/delete/', views.remove_message_view, name='remove_message'),
    path('<int:chat_id>/delete/', views.remove_chat_view, name='remove_chat'),
]