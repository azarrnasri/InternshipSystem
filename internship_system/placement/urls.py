"""
URL configuration for internship_system project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path
from django.shortcuts import redirect
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_redirect, name='dashboard'),  # redirect based on role
    path('student/dashboard/', views.student_dashboard, name='student_dashboard'),
    path('student/profile/', views.student_profile, name='student_profile'),
    path('student/internships/', views.internship_list, name='internship_list'),
    path('student/internship/<int:id>/apply/', views.apply_internship, name='apply_internship'),
    path('company/', views.company_dashboard, name='company_dashboard'),
    path('academic/', views.academic_dashboard, name='academic_dashboard'),
    path('manager/', views.admin, name='admin'),
    path('manager/users/', views.admin_user_list, name='admin_user_list'),
    path('manager/users/add/', views.admin_add_user, name='admin_add_user'),
    path('manager/users/delete/<int:user_id>/', views.admin_user_delete, name='admin_user_delete'),
    path('manager/users/edit/<int:user_id>/', views.admin_add_user, name='admin_user_edit'),
    path('manager/companies/', views.admin_company_list, name='admin_company_list'),
    path('manager/companies/add/', views.admin_add_company, name='admin_add_company'),
    path('manager/companies/edit/<int:company_id>/', views.admin_edit_company, name='admin_edit_company'),
    path('manager/companies/delete/<int:company_id>/', views.admin_delete_company, name='admin_delete_company'),
    # Add this redirect
    path('academic/', lambda request: redirect('academic_dashboard')),

    path('academic/student/<int:student_id>/', views.academic_student_detail, name='academic_student_detail'),
    path('academic/evaluation/<int:eval_id>/submit/', views.submit_academic_evaluation, name='submit_academic_evaluation'),
]
