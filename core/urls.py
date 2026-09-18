from django.urls import path
from core import views

app_name = 'core'

urlpatterns = [
    path('', views.index_view, name="index"),
    path('/publication_detail', views.publication_detail_view, name='publication_detail'),
    path('/publication_list', views.publication_list_view, name='publication_list')
]