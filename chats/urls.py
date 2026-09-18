from django.urls import path
from . import views

app_name = 'chats'

urlpatterns = [
    path('', views.chat_list, name='list'),
    path('<int:chat_id>/', views.chat_detail, name='detail'),
    path('start/publication/<int:publication_id>/', views.start_chat_from_publication, name='start_from_publication'),
    path('start/user/<int:user_id>/', views.start_free_chat, name='start_free_chat'),
]