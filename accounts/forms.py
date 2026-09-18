from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django import forms
from .models import User

# форма регистрации
class UserRegistrationForm(UserCreationForm):

    class Meta:
        model = User
        fields = ('username', 'email', 'phone', 'city', 'avatar', 'password1', 'password2')

# форма редактирования
class UserUpdateForm(forms.ModelForm):

    class Meta:
        model = User
        fields = ('username', 'email', 'phone', 'city', 'avatar')

# форма входа
class UserLoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Логин'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Пароль'}))