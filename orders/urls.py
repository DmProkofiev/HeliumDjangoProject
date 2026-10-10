from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    path('', views.order_list_view, name='list'),
    path('<int:order_id>/', views.order_detail_view, name='detail'),
    path('checkout/', views.checkout_view, name='checkout'),
    path('payment/<int:payment_id>/', views.payment_detail_view, name='payment_detail'),
    path('payment/<int:payment_id>/pay/', views.pay_payment_view, name='pay_payment'),
    path('payment/<int:payment_id>/return/', views.payment_return_view, name='payment_return'),
    path('<int:order_id>/confirm/', views.confirm_order_view, name='confirm'),
    path('<int:order_id>/cancel/', views.cancel_order_view, name='cancel'),
    path('webhook/yookassa/', views.yookassa_webhook_view, name='yookassa_webhook'),
]