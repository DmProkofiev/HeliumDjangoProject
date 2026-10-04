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
    path('payment-methods/<int:method_id>/default/', views.set_default_payment_method_view, name='payment_method_default'),
    path('payment-methods/<int:method_id>/remove/', views.remove_payment_method_view, name='payment_method_remove'),
]