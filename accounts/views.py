from django.shortcuts import render

def login_view(request):
    return render(request, 'index.html')

def register_view(request):
    return render(request, 'index.html')

def profile_view(request):
    return render(request, 'index.html')

def logout_view(request):
    return render(request, 'index.html')
