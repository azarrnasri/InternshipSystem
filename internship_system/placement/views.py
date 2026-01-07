# Create your views here.
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .decorators import role_required
from .models import (
    Student, 
    Logbook, 
    Attendance, 
    PerformanceEvaluation, 
    AcademicSupervisor
)


# --- Login View ---
def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('dashboard')
        else:
            return render(request, 'login.html', {'error': 'Invalid username or password'})
    return render(request, 'login.html')

# --- Logout View ---
def logout_view(request):
    logout(request)
    return redirect('login')

# --- Redirect based on role ---
@login_required
def dashboard_redirect(request):
    user = request.user
    if user.role == 'student':
        return redirect('student_dashboard')
    elif user.role == 'company':
        return redirect('company_dashboard')
    elif user.role == 'academic':
        return redirect('academic_dashboard')
    elif user.role == 'admin':
        return redirect('/admin/')  # redirect to Django admin
    else:
        return redirect('login')

# --- Individual dashboards ---
@role_required(allowed_roles=['student'])
def student_dashboard(request):
    context = {
        'placement_status': 'Not Assigned',
        'application_count': 0,
        'logbook_status': 'Not Submitted',
        'notification_count': 0,
    }
    return render(request, 'student/dashboard.html', context)

@login_required
@role_required(allowed_roles=['company'])
def company_dashboard(request):
    return render(request, 'company_dashboard.html')

@login_required
@role_required(allowed_roles=['academic'])
def academic_dashboard(request):
    supervisor = request.user.academicsupervisor

    # All students assigned to this supervisor
    students = Student.objects.filter(academic_supervisor=supervisor)

    # Pending logbooks (no academic notes yet)
    pending_logbooks = Logbook.objects.filter(
        student__in=students,
        academic_supervisor_notes__isnull=True
    )

    # Pending performance evaluations
    pending_evals = PerformanceEvaluation.objects.filter(
        academic_supervisor=supervisor,
        academic_supervisor_submitted_at__isnull=True
    )

    context = {
        'students': students,
        'pending_logbooks': pending_logbooks,
        'pending_evals': pending_evals,
    }

    return render(request, 'academic_dashboard.html', context)

def academic_student_detail(request, student_id):
    supervisor = request.user.academicsupervisor
    student = get_object_or_404(Student, id=student_id, academic_supervisor=supervisor)

    # Logbooks
    logbooks = Logbook.objects.filter(student=student)

    # Attendance records via placement
    attendance_records = Attendance.objects.filter(placement__student=student)

    # Performance evaluations
    evaluations = PerformanceEvaluation.objects.filter(student=student)

    context = {
        'student': student,
        'logbooks': logbooks,
        'attendance_records': attendance_records,
        'evaluations': evaluations
    }

    return render(request, 'academic_student_detail.html', context)

def submit_academic_evaluation(request, eval_id):
    evaluation = get_object_or_404(
        PerformanceEvaluation,
        id=eval_id,
        academic_supervisor=request.user.academicsupervisor
    )

    if request.method == 'POST':
        evaluation.academic_supervisor_score = request.POST.get('score')
        evaluation.academic_supervisor_comment = request.POST.get('comment')
        evaluation.academic_supervisor_submitted_at = timezone.now()
        evaluation.save()
        return redirect('academic_student_detail', student_id=evaluation.student.id)