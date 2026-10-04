from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    path('webhook/yookassa/', views.yookassa_webhook_view, name='yookassa_webhook'),
]