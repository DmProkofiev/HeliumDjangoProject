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

    # Способы оплаты
    path('payment-methods/add/', views.payment_method_add_view, name='payment_method_add'),
    path('payment-methods/<int:method_id>/edit/', views.payment_method_edit_view, name='payment_method_edit'),
    path('payment-methods/<int:method_id>/remove/', views.payment_method_remove_view, name='payment_method_remove'),
    path('payment-methods/<int:method_id>/default/', views.payment_method_default_view, name='payment_method_default'),
    path('payment-methods/<int:method_id>/binding-return/', views.payment_method_binding_return_view, name='payment_method_binding_return'),
    path('payment-methods/<int:method_id>/check-binding/', views.payment_method_check_binding_view, name='payment_method_check_binding'),
    path('webhook/yookassa-binding/', views.yookassa_binding_webhook_view, name='yookassa_binding_webhook'),

    # Публичный профиль
    path('user/<str:username>/', views.account_user_detail_view, name='account_user_detail'),

    # Администрирование: пользователи
    path('admin/users/<int:user_id>/toggle-block/', views.admin_toggle_user_block_view, name='admin_toggle_user_block'),

    # Администрирование: публикации
    path('admin/publications/<slug:slug>/edit/', views.admin_publication_update_view, name='admin_publication_update'),
    path('admin/publications/<slug:slug>/freeze/', views.admin_freeze_publication_view, name='admin_freeze_publication'),
    path('admin/publications/<slug:slug>/unfreeze/', views.admin_unfreeze_publication_view, name='admin_unfreeze_publication'),
    path('admin/publications/<slug:slug>/delete/', views.admin_delete_publication_view, name='admin_delete_publication'),
]