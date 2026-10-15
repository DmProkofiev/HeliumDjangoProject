from django.urls import path
from core import views

app_name = 'core'

urlpatterns = [
    path('', views.feed_view, name="feed"),
    path('publication_detail/<slug:slug>/', views.publication_detail_view, name='publication_detail'),
    path('publication_list/', views.publication_list_view, name='publication_list'),
    path('publications/create/', views.publication_create_view, name='publication_create'),
    path('publications/<slug:slug>/edit/', views.publication_update_view, name='publication_update'),
    path('publications/<slug:slug>/remove/', views.publication_remove_view, name='publication_remove'),
    path('publications/<slug:slug>/image/<int:index>/remove/', views.publication_image_remove_view, name='publication_image_remove'),
    path('publications/<slug:slug>/image/<int:index>/set-main/', views.publication_image_set_main_view, name='publication_image_set_main'),
    path('publications/', views.publication_list_view, name='publication_list'),
]