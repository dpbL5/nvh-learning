from django.shortcuts import render, redirect
from django.contrib.auth import logout


def home_view(request):
    return render(request, 'home.html')


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'login.html')


def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'register.html')


def dashboard_view(request):
    return render(request, 'dashboard.html')


def classes_view(request):
    return render(request, 'classes.html')


def admin_panel_view(request):
    return render(request, 'admin_panel.html')


def class_detail_view(request, class_id):
    return render(request, 'class_detail.html', {'class_id': str(class_id)})


def quiz_builder_view(request, quiz_id):
    return render(request, 'quiz_builder.html', {'quiz_id': str(quiz_id)})

def quiz_taker_view(request, quiz_id):
    return render(request, 'quiz_taker.html', {'quiz_id': str(quiz_id)})

def question_bank_view(request):
    return render(request, 'question_bank.html')

def logout_view(request):
    logout(request)
    return redirect('/login/')

def notifications_view(request):
    return render(request, 'notifications.html')
