from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from core.models import Publication
from .forms import UserRegistrationForm, UserUpdateForm, UserLoginForm
from .models import Favorite, Cart, User
from django.contrib import messages
from django.views.decorators.http import require_POST
from .models import PaymentMethod


def login_view(request):
    if request.user.is_authenticated:
        return redirect('core:feed')
    form = UserLoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        login(request, user)
        next_url = request.GET.get('next') or request.POST.get('next')
        return redirect(next_url or 'core:feed')
    return render(request, 'accounts/login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('core:feed')

def register_view(request):
    if request.user.is_authenticated:
        return redirect('core:feed')
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('core:feed')
    else:
        form = UserRegistrationForm()
    return render(request, 'accounts/register.html', {'form': form})

@login_required
def profile_view(request):
    user = request.user
    my_publications = Publication.objects.filter(author=user).order_by('-created_at')
    favorites = Favorite.objects.filter(user=user).select_related('publication', 'publication__author', 'publication__category')
    cart_items = Cart.objects.filter(user=user).select_related('publication', 'publication__author', 'publication__category')
    payment_methods = user.payment_methods.all()
    context = {
        'my_publications': my_publications,
        'favorites': favorites,
        'cart_items': cart_items,
        'payment_methods': payment_methods,
    }
    return render(request, 'accounts/account_detail.html', context)

@login_required
def profile_edit_view(request):
    if request.method == 'POST':
        form = UserUpdateForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('accounts:profile')
    else:
        form = UserUpdateForm(instance=request.user)
    return render(request, 'accounts/profile_edit.html', {'form': form})

@login_required
@require_POST
def toggle_like(request, publication_id):
    publication = get_object_or_404(Publication, id=publication_id)
    like, created = Favorite.objects.get_or_create(user=request.user,publication=publication)
    if not created:
        like.delete()
    return redirect(request.META.get('HTTP_REFERER', 'core:feed'))

@login_required
@require_POST
def toggle_cart(request, publication_id):
    publication = get_object_or_404(Publication, id=publication_id)
    item = Cart.objects.filter(user=request.user, publication=publication).first()
    if item:
        item.delete()
    else:
        Cart.objects.create(user=request.user, publication=publication)
    return redirect(request.META.get('HTTP_REFERER', 'core:feed'))

@login_required
@require_POST
def set_default_payment_method_view(request, method_id):
    method = get_object_or_404(PaymentMethod, id=method_id, user=request.user)
    method.is_default = True
    method.save()
    messages.success(request, 'Карта выбрана по умолчанию')
    return redirect('accounts:profile')

@login_required
@require_POST
def remove_payment_method_view(request, method_id):
    method = get_object_or_404(PaymentMethod, id=method_id, user=request.user)
    method.delete()
    messages.success(request, 'Способ оплаты удалён')
    return redirect('accounts:profile')