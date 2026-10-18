from django.urls import path
from accounts import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='account_detail'),
    path('profile/edit/', views.profile_edit_view, name='profile_edit'),
    path('like/<int:publication_id>/toggle/', views.toggle_like, name='toggle_like'),
    path('cart/<int:publication_id>/toggle/', views.toggle_cart, name='toggle_cart'),
    path('payment-methods/add/', views.payment_method_add_view, name='payment_method_add'),
    path('payment-methods/<int:method_id>/edit/', views.payment_method_edit_view, name='payment_method_edit'),
    path('payment-methods/<int:method_id>/remove/', views.payment_method_remove_view, name='payment_method_remove'),
    path('payment-methods/<int:method_id>/default/', views.payment_method_default_view, name='payment_method_default'),
    path('payment-methods/<int:method_id>/binding-return/', views.payment_method_binding_return_view, name='payment_method_binding_return'),
    path('webhook/yookassa-binding/', views.yookassa_binding_webhook_view, name='yookassa_binding_webhook'),
    path('user/<str:username>/', views.account_user_detail_view, name='account_user_detail'),
]