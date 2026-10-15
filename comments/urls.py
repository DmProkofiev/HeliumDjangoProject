from django.urls import path
from . import views

app_name = 'comments'

urlpatterns = [
    path('publication/<slug:slug>/add/', views.comment_create_view, name='comment_create'),
    path('<int:pk>/edit/', views.comment_update_view, name='comment_update'),
    path('<int:pk>/delete/', views.comment_delete_view, name='comment_delete'),
    path('<int:pk>/image/<int:index>/remove/', views.comment_image_remove_view, name='comment_image_remove'),
]