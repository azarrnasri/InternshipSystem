from django.contrib import admin
from .models import *

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'role')
    search_fields = ('username', 'email')
    list_filter = ('role',)

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('user', 'program', 'semester', 'academic_supervisor')
    search_fields = ('user__username', 'program')

@admin.register(AcademicSupervisor)
class AcademicSupervisorAdmin(admin.ModelAdmin):
    list_display = ('user', 'department')

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('company_name',)

@admin.register(CompanySupervisor)
class CompanySupervisorAdmin(admin.ModelAdmin):
    list_display = ('user', 'company')

@admin.register(Internship)
class InternshipAdmin(admin.ModelAdmin):
    list_display = ('title', 'company', 'status', 'start_date', 'end_date')
    list_filter = ('status', 'company')

@admin.register(InternshipApplication)
class InternshipApplicationAdmin(admin.ModelAdmin):
    list_display = ('student', 'internship', 'status', 'applied_date')
    list_filter = ('status',)

@admin.register(InternshipPlacement)
class InternshipPlacementAdmin(admin.ModelAdmin):
    list_display = ('student', 'internship', 'company_supervisor', 'status')

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('placement', 'date', 'check_in', 'check_out')

@admin.register(Logbook)
class LogbookAdmin(admin.ModelAdmin):
    list_display = ('student', 'week_no', 'submitted_date', 'company_approval')

@admin.register(PerformanceEvaluation)
class PerformanceEvaluationAdmin(admin.ModelAdmin):
    list_display = ('student', 'company_supervisor_score', 'academic_supervisor_score')

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('student', 'doc_type', 'upload_date')

