from django.urls import path
from core import views

app_name = 'core'

urlpatterns = [
    path('', views.feed_view, name="feed"),
    path('publication_detail/<slug:slug>/', views.publication_detail_view, name='publication_detail'),
    path('/publication_list', views.publication_list_view, name='publication_list')
]