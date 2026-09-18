from django.urls import path
from accounts import views

app_name = 'accounts'

urlpatterns = [
    path('accounts/login', views.login_view, name="login"),
    path('accounts/register', views.register_view, name='register'),
    path('accounts/profile', views.profile_view, name='profile'),
    path('accounts/logout', views.logout_view, name='logout')
]