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
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/read/<int:pk>/', views.mark_notification_read, name='mark_notification_read'),

    path('student/dashboard/', views.student_dashboard, name='student_dashboard'),
    path('student/profile/', views.student_profile, name='student_profile'),
    path('student/profile/email/', views.update_email, name='update_email'),
    path('student/profile/upload/', views.upload_document, name='upload_document'),
    path('document/edit/<int:doc_id>/', views.edit_document, name='edit_document'),
    path('document/delete/<int:doc_id>/', views.delete_document, name='delete_document'),
    path('student/internships/', views.internship_list, name='internship_list'),
    path('student/internship/<int:id>/apply/', views.apply_internship, name='apply_internship'),
    path('student/offers/', views.student_offers, name='student_offers'),
    path('student/offers/<int:pk>/accept/', views.accept_offer, name='accept_offer'),
    path('student/offers/<int:pk>/reject/', views.reject_offer, name='reject_offer'),
    path('student/logbook/', views.logbook_list, name='logbook_list'),
    path('student/logbook/submit/<int:week_no>/', views.submit_logbook, name='submit_logbook'),
    path('student/logbook/edit/<int:id>/', views.edit_logbook, name='edit_logbook'),
    path('student/attendance/', views.student_attendance_summary, name='student_attendance_summary'),

    path('company/', views.company_dashboard, name='company_dashboard'),
    path('student/profile/<int:student_id>/', views.student_profile, name='company_student_profile'),
    path('company/attendance/', views.interns_attendance, name='interns_attendance'),
    path('company/attendance_summary/', views.attendance_summary, name='attendance_summary'),
    path('company/evaluation/', views.intern_evaluation_list, name='evaluation_list'),
    path('company/evaluation_form/<int:placement_id>', views.evaluate_intern, name='interns_evaluation'),
    path('company/applications/', views.supervisor_applications, name='supervisor_applications'),
    path('company/application/<int:application_id>/offer/', views.supervisor_decide, name='offer_application'),
    path('company/logbooks/', views.company_logbook_review, name='company_logbook_review'),
    path('company/logbook/review/<int:logbook_id>/', views.review_logbook, name='review_logbook'),


    path('academic/', views.academic_dashboard, name='academic_dashboard'),
    path('academic/logbooks/', views.academic_logbook_review, name='academic_logbook_review'),

    path('manager/', views.admin, name='admin'),
    path('manager/users/', views.admin_user_list, name='admin_user_list'),
    path('manager/users/add/', views.admin_add_user, name='admin_add_user'),
    path('manager/users/delete/<int:user_id>/', views.admin_user_delete, name='admin_user_delete'),
    path('manager/users/edit/<int:user_id>/', views.admin_add_user, name='admin_user_edit'),
    path('manager/companies/', views.admin_company_list, name='admin_company_list'),
    path('manager/companies/add/', views.admin_add_company, name='admin_add_company'),
    path('manager/companies/edit/<int:company_id>/', views.admin_edit_company, name='admin_edit_company'),
    path('manager/companies/delete/<int:company_id>/', views.admin_delete_company, name='admin_delete_company'),
    path('manager/internships/', views.admin_internships_list, name='admin_internships_list'),
    path('manager/internships/add/', views.admin_add_internship, name='admin_add_internship'),
    path('manager/internships/edit/<int:internship_id>/', views.admin_edit_internship, name='admin_edit_internship'),
    path('manager/internships/delete/<int:internship_id>/', views.admin_delete_internship, name='admin_delete_internship'),
    # AJAX endpoint for departments
    path('manager/departments/by-company/<int:company_id>/', views.departments_by_company, name='departments_by_company'),
    # Internship Placements (Admin)
    path('manager/applications/', views.admin_applications_list, name='admin_applications_list'),
    path('manager/applications/<int:application_id>/', views.admin_application_detail, name='admin_application_detail'),
    path('manager/applications/<int:application_id>/delete/', views.admin_delete_application, name='admin_delete_application'),
    path('manager/applications/<int:application_id>/replace-supervisor/', views.admin_replace_supervisor, name='admin_replace_supervisor'),

    path('manager/placements/', views.admin_internship_placements_list, name='admin_internship_placements_list'),
    path('manager/placements/manage/<int:placement_id>/', views.admin_manage_placement, name='admin_manage_placement'),
    path('manager/attendance/', views.admin_attendance_list, name='admin_attendance_list'),
    path('manager/attendance/manage/<int:internship_id>/', views.admin_manage_attendance, name='admin_attendance_manage'),
    path('manager/logbooks/', views.admin_logbooks_list, name='admin_logbooks_list'),
    path('manager/logbooks/manage/', views.admin_logbooks_manage, name='admin_logbooks_manage'),
    path('manager/evaluations/manage/', views.admin_evaluations_manage, name='admin_evaluations_manage'),







    
    path('academic/dashboard/', views.academic_dashboard, name='academic_dashboard'),
    # Add this redirect
    path('academic/', lambda request: redirect('academic_dashboard')),
    path('academic/dashboard/', views.academic_dashboard, name='academic_dashboard'),
    path('academic/student/<int:student_id>/', views.academic_student_detail, name='academic_student_detail'),
    path('academic/evaluation/<int:eval_id>/submit/', views.submit_academic_evaluation, name='submit_academic_evaluation'),
    
    path('academic/students/', views.academic_student_list, name='academic_student_list'),
    path('academic/student/<int:student_id>/evaluation/', views.academic_performance_evaluation, name='academic_performance_evaluation'),
    path('academic/student/<int:student_id>/attendance/', views.academic_student_attendance, name='academic_student_attendance'),
    path('academic/student/<int:student_id>/records/',views.academic_records,name='academic_records'),
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/read/<int:pk>/', views.mark_notification_read, name='mark_notification_read'),
]
