
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction, models
from django.views.decorators.http import require_POST
from django.db.models import Q, Prefetch, Exists, OuterRef, Count
from django.utils import timezone
from .decorators import role_required
from .forms import AdminUserForm, StudentForm, AcademicSupervisorForm, CompanySupervisorForm, StudentProfileForm, DocumentUploadForm, InternshipApplicationForm, InternshipForm, InternshipPlacementForm
from django.utils.timezone import now, localtime
from datetime import timedelta, date, datetime
from django.http import JsonResponse, HttpResponseForbidden
from .models import (
    User,
    Student, 
    Logbook, 
    Attendance, 
    PerformanceEvaluation, 
    AcademicSupervisor,
    AcademicRecord,
    CompanySupervisor,
    Company,
    Document,
    Internship,
    InternshipApplication,
    InternshipPlacement,
    Department,
    Notification
)

def departments_by_company(request, company_id):
    """Return JSON list of departments for a given company."""
    departments = Department.objects.filter(company_id=company_id).values('id', 'name')
    return JsonResponse(list(departments), safe=False)

def application_has_placement(application):
    return InternshipPlacement.objects.filter(
        student=application.student,
        internship=application.internship
    ).exists()

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
        return redirect('admin')  
    else:
        return redirect('login')

# --- Individual dashboards ---
@login_required
@role_required(allowed_roles=['student'])
def student_dashboard(request):
    student = request.user.student

    # Placement status
    placement = InternshipPlacement.objects.filter(
        student=student,
        status='Active'
    ).first()

    placement_status = 'Assigned' if placement else 'Not Assigned'

    # Total internship applications
    application_count = InternshipApplication.objects.filter(
        student=student
    ).count()

    # Logbook status (latest submission)
    latest_logbook = Logbook.objects.filter(
        student=student
    ).order_by('-submitted_date').first()

    if latest_logbook:
        logbook_status = latest_logbook.status
    else:
        logbook_status = 'Not Submitted'

    # Unread notifications
    notification_count = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).count()

    context = {
        'placement_status': placement_status,
        'application_count': application_count,
        'logbook_status': logbook_status,
        'notification_count': notification_count,
    }

    return render(request, 'student/dashboard.html', context)

@login_required
@role_required(allowed_roles=['company'])
def company_dashboard(request):
    try:
        #Logged-in company supervisor
        company_supervisor = CompanySupervisor.objects.get(user=request.user)
        company = company_supervisor.company
        profile_missing = False
    except CompanySupervisor.DoesNotExist:
        return render(
            request,
            'company/dashboard.html',
            {
                'total_interns': 0,
                'pending_applications': 0,
                'pending_logbooks': 0,
                'attendance_not_marked': 0,
                'interns': [],
                'pending_evaluation': 0,
                'profile_missing': True,
            }
        )

    #1. Total active interns
    total_interns = InternshipPlacement.objects.filter(
        company_supervisor = company_supervisor,
        status = 'Active'
    ).count()

    #2. Pending internship applications
    pending_applications = InternshipApplication.objects.filter(
        #internship__company = company,
        internship__department=company_supervisor.department,
        status = 'Pending'
    ).count()

    #3. Pending logbooks
    pending_logbooks = Logbook.objects.filter(
        application__internship__company = company,
        company_approval__isnull =  True
    ).count()

    #4. Attendance that has not marked yet
    today = now().date()

    attendance_not_marked = InternshipPlacement.objects.filter(
        company_supervisor = company_supervisor,
        status = 'Active'
    ).exclude(
        attendance__date = today
    ).count()

    #5. Pending evaluation
    pending_evaluation = PerformanceEvaluation.objects.filter(
        company_supervisor = request.user.companysupervisor,
        company_supervisor_submitted_at__isnull = True
    ).count()

    return render(
        request,
        'company/dashboard.html',
        {
            'total_interns': total_interns,
            'pending_applications': pending_applications,
            'pending_logbooks': pending_logbooks,
            'attendance_not_marked': attendance_not_marked,
            'pending_evaluation': pending_evaluation,
            'profile_missing': False,
        }
    )

@login_required
@role_required(allowed_roles=['company'])
def interns_attendance(request):
    today = now().date()

    try:
        company_supervisor = CompanySupervisor.objects.get(user=request.user)
    except CompanySupervisor.DoesNotExist:
        return render(request, 'company/attendance.html', {
            'profile_missing': True,
            'placements': [],
            'today': today,
        })

    # Active interns 
    placements = InternshipPlacement.objects.filter(
        company_supervisor = company_supervisor,
        status='Active'
    ).select_related('student__user')

    # Prefetch today's attendance only
    placements = placements.prefetch_related(
        Prefetch(
            'attendance_set',
            queryset=Attendance.objects.filter(date=today),
            to_attr='today_attendance'
        )
    )

    if request.method == 'POST':
        placement_id = request.POST.get('placement_id')
        action = request.POST.get('action')

        placement = get_object_or_404(
            InternshipPlacement,
            id=placement_id,
            company_supervisor = company_supervisor
        )

        attendance, created = Attendance.objects.get_or_create(
            placement = placement,
            date = today,
            defaults={'check_in': localtime(now()).time()}
        )

        if action == 'checkout' and attendance.check_out is None:
            attendance.check_out = localtime(now()).time()
            attendance.save()

        return redirect('interns_attendance')

    context = {
        'placements': placements,
        'today': today,
        'profile_missing': False,
    }

    return render(request, 'company/attendance.html', context)

@login_required
@role_required(allowed_roles=['company'])
def attendance_summary(request):
    date = request.GET.get('date', now().date())

    try:
        company_supervisor = CompanySupervisor.objects.get(user=request.user)
    except CompanySupervisor.DoesNotExist:
        return render(request, 'company/attendance_summary.html', {
            'profile_missing': True,
            'placements': [],
            'selected_date': date,
        })

    placements = InternshipPlacement.objects.filter(
        company_supervisor=company_supervisor,
        status='Active'
    ).select_related('student__user').prefetch_related(
        Prefetch(
            'attendance_set',
            queryset=Attendance.objects.filter(date=date),
            to_attr='attendance_for_date'
        )
    )

    context = {
        'placements': placements,
        'selected_date': date,
        'profile_missing': False,
    }

    return render(request, 'company/attendance_summary.html',context)

@login_required
@role_required(allowed_roles=['company'])
def intern_evaluation_list(request):
    try:
        company = CompanySupervisor.objects.get(user=request.user)
    except CompanySupervisor.DoesNotExist:
        return render(request, 'company/evaluation.html', {
            'placements': [],
            'profile_missing': True
        })

    placements = InternshipPlacement.objects.filter(
        company_supervisor = company
    ).select_related('student')

    today = timezone.now().date()
    for placement in placements:
        placement.is_evaluated = PerformanceEvaluation.objects.filter(
            application__student = placement.student,
            company_supervisor = company,
            company_supervisor_submitted_at__isnull=False
        ).exists()

        # Allow evaluation if active and within 1 week of end date
        days_left = (placement.end_date - today).days
        placement.can_evaluate = placement.status == 'Active' and days_left <= 7

    context = {
        'placements': placements,
        'profile_missing': False
    }

    return render(request, 'company/evaluation.html', context)

@login_required
@role_required(allowed_roles=['company'])
def evaluate_intern(request, placement_id):
    placement = get_object_or_404(
        InternshipPlacement,
        id = placement_id,
        company_supervisor__user=request.user
    )

    evaluation, created = PerformanceEvaluation.objects.get_or_create(
        student = placement.student,
        company_supervisor = placement.company_supervisor,
        academic_supervisor = placement.student.academic_supervisor,
        application=InternshipApplication.objects.filter(
            student = placement.student,
            internship = placement.internship
        ).first()
    )

    if evaluation.company_supervisor_submitted_at:
        return redirect('evaluation_list')

    if request.method == 'POST':
        evaluation.company_supervisor_score = request.POST['score']
        question_answers = {
            'q1': int(request.POST['q1']),
            'q2': int(request.POST['q2']),
            'q3': int(request.POST['q3']),
            'q4': int(request.POST['q4']),
            'q5': int(request.POST['q5']),
        }

        evaluation.company_question_answers = question_answers
        evaluation.company_supervisor_comment = request.POST.get('comment')
        evaluation.company_supervisor_submitted_at = now()
        evaluation.save()

        # Notify academic supervisor if exists
        if evaluation.academic_supervisor:
            Notification.objects.create(
                user=evaluation.academic_supervisor.user,
                message=f"Company Supervisor has submitted evaluation form for {evaluation.student.user.username}."
            )

        return redirect('evaluation_list')

    return render(request, 'company/evaluation_form.html', {
        'placement': placement
    })

@login_required
@role_required(allowed_roles=['academic'])
def academic_dashboard(request):
    supervisor = request.user.academicsupervisor

    students = Student.objects.filter(academic_supervisor=supervisor)

    pending_logbooks = Logbook.objects.filter(
        student__in=students,
        academic_supervisor_notes__isnull=True
    )

    pending_evals = PerformanceEvaluation.objects.filter(
        academic_supervisor=supervisor,
        academic_supervisor_submitted_at__isnull=True
    )

    context = {
        'students': students,
        'pending_logbooks': pending_logbooks,
        'pending_evals': pending_evals,
    }

    return render(request, 'academic/academic_dashboard.html', context)



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

    return render(request, 'academic/academic_student_detail.html', context)


def submit_academic_evaluation(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    academic_supervisor = request.user.academicsupervisor

    # Create a new evaluation or get existing one for this student and supervisor
    evaluation, created = PerformanceEvaluation.objects.get_or_create(
        student=student,
        academic_supervisor=academic_supervisor,
        defaults={
            'company_supervisor': student.internship.company.supervisor if hasattr(student, 'internship') else None,
            'application': student.internship.application if hasattr(student, 'internship') else None,
        }
    )

    if request.method == 'POST':
        # Save detailed scores & comments from the form
        evaluation.company_question_answers = {
            'attendance': {
                'score': int(request.POST.get('attendance_score', 0)),
                'comment': request.POST.get('attendance_comment', ''),
            },
            'punctuality': {
                'score': int(request.POST.get('punctuality_score', 0)),
                'comment': request.POST.get('punctuality_comment', ''),
            },
            'work_quality': {
                'score': int(request.POST.get('work_quality_score', 0)),
                'comment': request.POST.get('work_quality_comment', ''),
            },
            'overall': {
                'score': int(request.POST.get('overall_score', 0)),
                'comment': request.POST.get('overall_comment', ''),
            },
        }

        evaluation.academic_supervisor_score = int(request.POST.get('overall_score', 0))
        evaluation.academic_supervisor_comment = request.POST.get('overall_comment', '')
        evaluation.academic_supervisor_submitted_at = timezone.now()
        evaluation.save()

        return redirect('academic_student_detail', student_id=student.id)

    # Render page with previous evaluations
    previous_evaluations = PerformanceEvaluation.objects.filter(student=student).order_by('-academic_supervisor_submitted_at')
    return render(request, 'academic/academic_performance_evaluation.html', {
        'student': student,
        'previous_evaluations': previous_evaluations,
        'evaluation': evaluation,
    })
    
@login_required
def academic_student_attendance(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    attendance_records = Attendance.objects.filter(
        placement__student=student
    ).order_by('-date')

    return render(request, 'academic/academic_student_attendance.html', {
        'student': student,
        'attendance_records': attendance_records,
    })

@login_required
def academic_records(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    academic_supervisor = get_object_or_404(
        AcademicSupervisor,
        user=request.user
    )

    records = AcademicRecord.objects.filter(student=student).order_by('-created_at')

    if request.method == 'POST':
        notes = request.POST.get('notes')
        if notes:
            AcademicRecord.objects.create(
                student=student,
                academic_supervisor=academic_supervisor,
                notes=notes
            )
            messages.success(request, "Academic record saved successfully.")
            return redirect('academic_records', student_id=student.id)

    return render(request, 'academic/academic_records.html', {
        'student': student,
        'records': records
    })

@login_required
@role_required(allowed_roles=['admin'])
def admin(request):
    # Summary metrics
    total_users = User.objects.count()
    students_count = User.objects.filter(role='student').count()
    companies_count = User.objects.filter(role='company').count()
    academics_count = User.objects.filter(role='academic').count()
    admins_count = User.objects.filter(role='admin').count()
    
    total_internships = Internship.objects.count()
    open_internships = Internship.objects.filter(status='Open').count()
    closed_internships = Internship.objects.filter(status='Closed').count()
    
    total_applications = InternshipApplication.objects.count()
    pending_applications = InternshipApplication.objects.filter(status='Pending').count()
    accepted_applications = InternshipApplication.objects.filter(status='Accepted').count()
    rejected_applications = InternshipApplication.objects.filter(status='Rejected').count()
    offered_applications = InternshipApplication.objects.filter(status='Offered').count()
    
    active_placements = InternshipPlacement.objects.filter(status='Active').count()
    completed_placements = InternshipPlacement.objects.filter(status='Completed').count()
    
    total_logbooks = Logbook.objects.count()
    pending_logbooks = Logbook.objects.filter(status='Pending').count()
    approved_logbooks = Logbook.objects.filter(status='Approved').count()
    rejected_logbooks = Logbook.objects.filter(status='Rejected').count()
    
    total_companies = Company.objects.count()
    total_departments = Department.objects.count()
    
    total_attendance = Attendance.objects.count()
    today_attendance = Attendance.objects.filter(date=timezone.now().date()).count()
    
    pending_evaluations = PerformanceEvaluation.objects.filter(
        Q(company_supervisor_submitted_at__isnull=True) | Q(academic_supervisor_submitted_at__isnull=True)
    ).count()
    
    # Recent notifications for admin
    recent_notifications = Notification.objects.filter(
        user=request.user
    ).order_by('-created_at')[:10]  # Last 10 notifications
    
    unread_notifications_count = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).count()
    
    context = {
        'total_users': total_users,
        'students_count': students_count,
        'companies_count': companies_count,
        'academics_count': academics_count,
        'admins_count': admins_count,
        'total_internships': total_internships,
        'open_internships': open_internships,
        'closed_internships': closed_internships,
        'total_applications': total_applications,
        'pending_applications': pending_applications,
        'accepted_applications': accepted_applications,
        'rejected_applications': rejected_applications,
        'offered_applications': offered_applications,
        'active_placements': active_placements,
        'completed_placements': completed_placements,
        'total_logbooks': total_logbooks,
        'pending_logbooks': pending_logbooks,
        'approved_logbooks': approved_logbooks,
        'rejected_logbooks': rejected_logbooks,
        'total_companies': total_companies,
        'total_departments': total_departments,
        'total_attendance': total_attendance,
        'today_attendance': today_attendance,
        'pending_evaluations': pending_evaluations,
        'recent_notifications': recent_notifications,
        'unread_notifications_count': unread_notifications_count,
    }
    return render(request, 'admin/admin.html', context)

@login_required
@role_required(allowed_roles=['admin'])
def admin_add_user(request, user_id=None):

    # --- Load user if editing ---
    if user_id:
        user = get_object_or_404(User, id=user_id)
    else:
        user = None

    # --- Load role instances ---
    student_instance = None
    academic_instance = None
    company_instance = None

    if user:
        if user.role == 'student':
            student_instance = getattr(user, 'student', None)
        elif user.role == 'academic':
            academic_instance = getattr(user, 'academicsupervisor', None)
        elif user.role == 'company':
            company_instance = getattr(user, 'companysupervisor', None)

    # --- ALWAYS initialize forms (GET + POST) ---
    user_form = AdminUserForm(
        request.POST or None,
        instance=user
    )

    student_form = StudentForm(
        request.POST or None,
        instance=student_instance
    )

    academic_form = AcademicSupervisorForm(
        request.POST or None,
        instance=academic_instance
    )

    company_form = CompanySupervisorForm(
        request.POST or None,
        instance=company_instance
    )

    # --- Handle POST ---
    if request.method == 'POST':
        if user_form.is_valid():
            role = user_form.cleaned_data['role']

            role_form_valid = (
                role == 'admin' or
                (role == 'student' and student_form.is_valid()) or
                (role == 'academic' and academic_form.is_valid()) or
                (role == 'company' and company_form.is_valid())
            )

            if role_form_valid:
                with transaction.atomic():
                    user = user_form.save(commit=False)

                    password = user_form.cleaned_data.get('password')
                    if password:
                        user.set_password(password)

                    user.save()

                    if role == 'student':
                        Student.objects.filter(user=user).update(
                            **student_form.cleaned_data
                        )

                    elif role == 'academic':
                        AcademicSupervisor.objects.filter(user=user).update(
                            **academic_form.cleaned_data
                        )

                    elif role == 'company':
                        CompanySupervisor.objects.filter(user=user).update(
                            **company_form.cleaned_data
                        )


                # Notify admin
                action = "added" if not user_id else "updated"
                Notification.objects.create(
                    user=request.user,
                    message=f"You {action} user {user.username} ({user.email})."
                )

                return redirect('admin_user_list')

    # --- Render page ---
    return render(request, 'admin/admin_user_form.html', {
        'user_form': user_form,
        'student_form': student_form,
        'academic_form': academic_form,
        'company_form': company_form,
        'is_edit': bool(user),
    })


@login_required
@role_required(allowed_roles=['admin'])
@require_POST
def admin_user_delete(request, user_id):
    user = get_object_or_404(User, id=user_id)

    # Optional safety: prevent deleting yourself
    if user == request.user:
        return redirect('admin_user_list')

    # Notify admin
    Notification.objects.create(
        user=request.user,
        message=f"You deleted user {user.username} ({user.email})."
    )

    user.delete()
    return redirect('admin_user_list')

@login_required
@role_required(allowed_roles=['admin'])
def admin_user_list(request):
    role_filter = request.GET.get('role', 'all')

    if role_filter == 'student':
        students = User.objects.filter(role='student').select_related('student')
        academics = User.objects.none()
        companies = User.objects.none()
        admins = User.objects.none()
    elif role_filter == 'academic':
        students = User.objects.none()
        academics = User.objects.filter(role='academic').select_related('academicsupervisor')
        companies = User.objects.none()
        admins = User.objects.none()
    elif role_filter == 'company':
        students = User.objects.none()
        academics = User.objects.none()
        companies = User.objects.filter(role='company').select_related('companysupervisor')
        admins = User.objects.none()
    elif role_filter == 'admin':
        students = User.objects.none()
        academics = User.objects.none()
        companies = User.objects.none()
        admins = User.objects.filter(role='admin')
    else:
        students = User.objects.filter(role='student').select_related('student')
        academics = User.objects.filter(role='academic').select_related('academicsupervisor')
        companies = User.objects.filter(role='company').select_related('companysupervisor')
        admins = User.objects.filter(role='admin')

    return render(request, 'admin/admin_user_list.html', {
        'students': students,
        'academics': academics,
        'companies': companies,
        'admins': admins,
        'selected_role': role_filter,
    })

@login_required
@role_required(allowed_roles=['admin'])
def admin_company_list(request):
    search = request.GET.get('search', '')
    companies = Company.objects.all()
    if search:
        companies = companies.filter(company_name__icontains=search)
    return render(request, 'admin/admin_company_list.html', {
        'companies': companies,
        'search': search,
    })


@login_required
@role_required(allowed_roles=['admin'])
def admin_add_company(request):
    if request.method == 'POST':
        company_name = request.POST.get('company_name')
        address = request.POST.get('address')

        if company_name and address:
            company = Company.objects.create(
                company_name=company_name,
                address=address
            )
            # Notify admin
            Notification.objects.create(
                user=request.user,
                message=f"You added company {company.company_name}."
            )
            return redirect('admin_company_list')

    return render(request, 'admin/admin_company_form.html')

@login_required
@role_required(allowed_roles=['admin'])
def admin_edit_company(request, company_id):
    company = get_object_or_404(Company, id=company_id)

    if request.method == 'POST':
        # 1️⃣ Update company
        company.company_name = request.POST.get('company_name')
        company.address = request.POST.get('address')
        company.save()

        # Notify admin
        Notification.objects.create(
            user=request.user,
            message=f"You updated company {company.company_name}."
        )

        # 2️⃣ Update existing departments
        dept_ids = request.POST.getlist('dept_id[]')
        dept_names = request.POST.getlist('dept_name[]')
        delete_ids = request.POST.getlist('dept_delete[]')

        for dept_id, name in zip(dept_ids, dept_names):
            if dept_id in delete_ids:
                Department.objects.filter(id=dept_id, company=company).delete()
            else:
                Department.objects.filter(id=dept_id, company=company).update(
                    name=name.strip()
                )

        # 3️⃣ Add new departments
        new_departments = request.POST.get('new_departments', '')
        if new_departments:
            for name in new_departments.split(','):
                name = name.strip()
                if name:
                    Department.objects.get_or_create(
                        company=company,
                        name=name
                    )

        return redirect('admin_company_list')

    return render(request, 'admin/admin_company_form.html', {
        'company': company,
        'is_edit': True
    })



@login_required
@role_required(allowed_roles=['admin'])
@require_POST
def admin_delete_company(request, company_id):
    company = get_object_or_404(Company, id=company_id)

    # Notify admin
    Notification.objects.create(
        user=request.user,
        message=f"You deleted company {company.company_name}."
    )

    company.delete()
    return redirect('admin_company_list')


@login_required
@role_required(allowed_roles=['admin'])
def admin_internships_list(request):
    company_id = request.GET.get('company')
    internships = (
        Internship.objects
        .select_related('company')
        .order_by('company__company_name', 'title')
    )
    if company_id:
        internships = internships.filter(company_id=company_id)

    companies = Company.objects.all().order_by('company_name')

    return render(
        request,
        'admin/admin_internships_list.html',
        {
            'internships': internships,
            'companies': companies,
            'selected_company': company_id,
        }
    )

@login_required
@role_required(allowed_roles=['admin'])
def admin_applications_list(request):
    company_id = request.GET.get('company')

    applications = (
        InternshipApplication.objects
        .select_related(
            'student__user',
            'internship',
            'internship__company',
            'internship__department',
            'handled_by__user',
        )
        .order_by(
            'internship__company__company_name',  # 1️⃣ group by company
            'internship__id',                     # 2️⃣ group by internship
            'created_at',                          # 3️⃣ stable order inside group
        )
    )

    if company_id:
        applications = applications.filter(internship__company_id=company_id)

    companies = Company.objects.all().order_by('company_name')

    return render(request, 'admin/admin_applications_list.html', {
        'applications': applications,
        'companies': companies,
        'selected_company': company_id,
    })



@login_required
@role_required(allowed_roles=['admin'])
def admin_application_detail(request, application_id):

    # 🔹 STEP 1: handle student switch (dropdown)
    switch_id = request.GET.get('application_switch')
    if switch_id:
        return redirect(
            'admin_application_detail',
            application_id=switch_id
        )

    # 🔹 STEP 2: load selected application
    application = get_object_or_404(InternshipApplication, id=application_id)
    has_placement = application_has_placement(application)

    # 🔹 STEP 3: all applications under the SAME internship
    related_applications = InternshipApplication.objects.filter(
        internship=application.internship
    ).select_related('student__user')

    # 🔹 STEP 4: supervisors filtered by company + department
    supervisors = CompanySupervisor.objects.filter(
        company=application.internship.company,
        department=application.internship.department
    )

    return render(request, 'admin/admin_application_detail.html', {
        'application': application,
        'related_applications': related_applications,
        'supervisors': supervisors,
        'has_placement': has_placement
    })




@login_required
@role_required(allowed_roles=['admin'])
def admin_delete_application(request, application_id):
    if request.user.role != 'admin':
        return redirect('dashboard')

    application = get_object_or_404(InternshipApplication, id=application_id)

    if application_has_placement(application):
        messages.error(request, "Cannot delete application after placement is created.")
        return redirect('admin_application_detail', application_id=application.id)

    # Notify admin
    Notification.objects.create(
        user=request.user,
        message=f"You deleted application from {application.student.user.username} for {application.internship.title} at {application.internship.company.company_name}."
    )

    application.delete()
    messages.success(request, "Application removed successfully.")
    return redirect('admin_applications_list')


@login_required
@role_required(allowed_roles=['admin'])
def admin_replace_supervisor(request, application_id):
    application = get_object_or_404(InternshipApplication, id=application_id)
    internship = application.internship

    # 🚫 Block if ANY placement exists for this internship
    if InternshipPlacement.objects.filter(internship=internship).exists():
        messages.error(
            request,
            "Cannot change supervisor. One or more placements already exist."
        )
        return redirect('admin_application_detail', application_id=application.id)

    if request.method == 'POST':
        supervisor = get_object_or_404(
            CompanySupervisor,
            id=request.POST.get('company_supervisor'),
            company=internship.company,
            department=internship.department
        )

        # 🔁 BULK UPDATE (this is the magic)
        InternshipApplication.objects.filter(
            internship=internship
        ).update(
            handled_by=supervisor,
            updated_at=timezone.now()
        )

        # Notify admin
        Notification.objects.create(
            user=request.user,
            message=f"You changed company supervisor to {supervisor.user.username} for internship {internship.title} at {internship.company.company_name}."
        )

        messages.success(
            request,
            "Company supervisor updated for all students in this internship."
        )

    return redirect('admin_application_detail', application_id=application.id)




@login_required
@role_required(allowed_roles=['admin'])
def admin_internship_placements_list(request):
    company_id = request.GET.get('company')

    placements = (
        InternshipPlacement.objects
        .select_related(
            'student__user',
            'internship__company',
            'internship__department',
            'company_supervisor__user',
        )
        .order_by('internship__company__company_name')
    )

    if company_id:
        placements = placements.filter(internship__company_id=company_id)

    companies = Company.objects.all().order_by('company_name')

    return render(
        request,
        'admin/admin_internship_placements.html',
        {
            'placements': placements,
            'companies': companies,
            'selected_company': company_id,
        }
    )

@login_required
@role_required(allowed_roles=['admin'])
def admin_manage_placement(request, placement_id):

    # 🔹 Placement switch (dropdown)
    switch_id = request.GET.get('placement_switch')
    if switch_id:
        return redirect(
            'admin_manage_placement',
            placement_id=switch_id
        )

    placement = get_object_or_404(
        InternshipPlacement.objects.select_related(
            'student__user',
            'internship__company',
            'internship__department',
            'company_supervisor__user',
        ),
        id=placement_id
    )

    placements_same_internship = InternshipPlacement.objects.filter(
        internship=placement.internship
    ).select_related('student__user')

    # ✅ ALWAYS initialize form
    form = InternshipPlacementForm(instance=placement)

    if request.method == 'POST':

        if "delete_placement" in request.POST:
            # Notify admin
            Notification.objects.create(
                user=request.user,
                message=f"You deleted placement for {placement.student.user.username} at {placement.internship.company.company_name}."
            )
            placement.delete()
            messages.success(request, "Placement deleted.")
            return redirect('admin_internship_placements_list')

        if "remove_student" in request.POST:
            remove_id = request.POST.get("remove_student_id")
            placement_to_remove = get_object_or_404(
                InternshipPlacement, id=remove_id
            )
            # Notify admin
            Notification.objects.create(
                user=request.user,
                message=f"You removed {placement_to_remove.student.user.username} from placement at {placement_to_remove.internship.company.company_name}."
            )
            placement_to_remove.delete()
            messages.success(request, "Student removed from placement.")
            return redirect('admin_manage_placement', placement_id=placement.id)

        if "save_changes" in request.POST:
            form = InternshipPlacementForm(request.POST, instance=placement)

            if form.is_valid():
                cleaned = form.cleaned_data

                InternshipPlacement.objects.filter(
                    internship=placement.internship
                ).update(
                    company_supervisor=cleaned['company_supervisor'],
                    start_date=cleaned['start_date'],
                    end_date=cleaned['end_date'],
                    status=cleaned['status'],
                    updated_at=timezone.now()
                )

                # Notify admin
                Notification.objects.create(
                    user=request.user,
                    message=f"You updated placements for internship {placement.internship.title} at {placement.internship.company.company_name}."
                )

                messages.success(
                    request,
                    "Placement updated for all students in this internship."
                )
                return redirect('admin_internship_placements_list')
            else:
                messages.error(request, "Please fix the errors below.")

    return render(
        request,
        'admin/admin_placement_manage.html',
        {
            'form': form,
            'placement': placement,
            'placements_same_internship': placements_same_internship,
            'is_edit': True,
        }
    )


@login_required
@role_required(allowed_roles=['admin'])
def admin_attendance_list(request):
    company_id = request.GET.get('company')

    placements = (
        InternshipPlacement.objects
        .select_related(
            'internship__company',
            'internship__department',
        )
        .order_by('internship__company__company_name')
    )

    if company_id:
        placements = placements.filter(internship__company_id=company_id)

    companies = Company.objects.all().order_by('company_name')

    return render(
        request,
        'admin/admin_attendance_list.html',
        {
            'placements': placements,
            'companies': companies,
            'selected_company': company_id,
        }
    )


@login_required
@role_required(allowed_roles=['admin'])
def admin_manage_attendance(request, internship_id):

    # 1️⃣ Internship anchor
    internship = get_object_or_404(
        Internship.objects.select_related('company', 'department'),
        id=internship_id
    )

    # 2️⃣ Placements under internship
    placements = InternshipPlacement.objects.filter(
        internship=internship
    ).select_related(
        'student__user',
        'company_supervisor__user'
    )

    selected_placement = None
    attendance_records = []

    placement_id = request.GET.get('placement')

    if placement_id:
        selected_placement = get_object_or_404(
            InternshipPlacement,
            id=placement_id,
            internship=internship
        )

        attendance_records = Attendance.objects.filter(
            placement=selected_placement
        ).order_by('-date')

    # 🔒 Lock if placement completed
    is_locked = selected_placement and selected_placement.status == 'Completed'

    if request.method == 'POST' and selected_placement:

        # 🗑 DELETE attendance
        if 'delete_attendance' in request.POST and not is_locked:
            attendance_id = request.POST.get('attendance_id')
            attendance = get_object_or_404(
                Attendance,
                id=attendance_id,
                placement=selected_placement
            )
            # Notify admin
            Notification.objects.create(
                user=request.user,
                message=f"You deleted attendance record for {selected_placement.student.user.username} on {attendance.date}."
            )
            attendance.delete()
            messages.success(request, "Attendance record deleted.")
            return redirect(
                f"{request.path}?placement={selected_placement.id}"
            )

        # ✏️ EDIT attendance
        if 'edit_attendance' in request.POST and not is_locked:
            attendance_id = request.POST.get('attendance_id')
            attendance = get_object_or_404(
                Attendance,
                id=attendance_id,
                placement=selected_placement
            )

            attendance.check_in = request.POST.get('check_in')
            attendance.check_out = request.POST.get('check_out')
            attendance.save(update_fields=['check_in', 'check_out', 'updated_at'])

            # Notify admin
            Notification.objects.create(
                user=request.user,
                message=f"You updated attendance for {selected_placement.student.user.username} on {attendance.date}."
            )

            messages.success(request, "Attendance updated.")
            return redirect(
                f"{request.path}?placement={selected_placement.id}"
            )

        # ➕ ADD attendance (optional)
        if 'add_attendance' in request.POST and not is_locked:
            attendance = Attendance.objects.create(
                placement=selected_placement,
                date=request.POST.get('date'),
                check_in=request.POST.get('check_in'),
                check_out=request.POST.get('check_out')
            )
            # Notify admin
            Notification.objects.create(
                user=request.user,
                message=f"You added attendance record for {selected_placement.student.user.username} on {attendance.date}."
            )
            messages.success(request, "Attendance added.")
            return redirect(
                f"{request.path}?placement={selected_placement.id}"
            )

    return render(
        request,
        'admin/admin_attendance_manage.html',
        {
            'internship': internship,
            'placements': placements,
            'selected_placement': selected_placement,
            'attendance_records': attendance_records,
            'is_locked': is_locked,
        }
    )


@login_required
@role_required(allowed_roles=['admin'])
def admin_logbooks_list(request):
    company_id = request.GET.get('company')

    placements = (
        InternshipPlacement.objects
        .select_related(
            'student__user',
            'internship__company',
            'internship__department',
            'company_supervisor__user',
        )
        .order_by('internship__company__company_name')
    )

    if company_id:
        placements = placements.filter(internship__company_id=company_id)

    companies = Company.objects.all().order_by('company_name')

    return render(
        request,
        'admin/admin_logbooks_list.html',
        {
            'placements': placements,
            'companies': companies,
            'selected_company': company_id,
        }
    )


@login_required
@role_required(allowed_roles=['admin'])
def admin_logbooks_manage(request):

    # Get filter params
    company_id = request.GET.get('company')
    internship_id = request.GET.get('internship')
    student_id = request.GET.get('student')

    # Get all for selects
    companies = Company.objects.all().order_by('company_name')
    internships = Internship.objects.select_related('company').order_by('company__company_name', 'title')
    students = User.objects.filter(role='student').order_by('username')

    # Filter internships and students based on selections
    if company_id:
        internships = internships.filter(company_id=company_id)
        students = students.filter(
            student__internshipplacement__internship__company_id=company_id
        ).distinct()

    if internship_id:
        students = students.filter(
            student__internshipplacement__internship_id=internship_id
        ).distinct()

    selected_student = None
    logbooks_by_internship = {}

    if student_id:
        selected_student = get_object_or_404(User, id=student_id, role='student')

        # Get logbooks for this student
        logbooks = Logbook.objects.filter(
            application__student__user=selected_student,
            application__status='Accepted'
        ).select_related(
            'application__internship__company'
        ).order_by('application__internship__title', 'week_no')

        # Group by internship
        for log in logbooks:
            internship = log.application.internship
            if internship not in logbooks_by_internship:
                logbooks_by_internship[internship] = []
            logbooks_by_internship[internship].append(log)

    # POST actions
    if request.method == 'POST' and selected_student:
        logbook_id = request.POST.get('logbook_id')

        if 'update_status' in request.POST:
            logbook = get_object_or_404(Logbook, id=logbook_id)
            old_status = logbook.status
            logbook.status = request.POST.get('status')
            logbook.save()
            # Notify admin
            Notification.objects.create(
                user=request.user,
                message=f"You updated logbook status for {logbook.application.student.user.username} week {logbook.week_no} from {old_status} to {logbook.status}."
            )

        elif 'delete_logbook' in request.POST:
            logbook = Logbook.objects.get(id=logbook_id)
            # Notify admin
            Notification.objects.create(
                user=request.user,
                message=f"You deleted logbook for {logbook.application.student.user.username} week {logbook.week_no}."
            )
            logbook.delete()

        return redirect(f"{request.path}?company={company_id or ''}&internship={internship_id or ''}&student={student_id}")

    return render(
        request,
        'admin/admin_logbooks_manage.html',
        {
            'companies': companies,
            'internships': internships,
            'students': students,
            'selected_company': company_id,
            'selected_internship': internship_id,
            'selected_student': selected_student,
            'logbooks_by_internship': logbooks_by_internship,
        }
    )




@login_required
@role_required(allowed_roles=['admin'])
def admin_evaluations_manage(request):

    # Get filter params
    company_id = request.GET.get('company')
    internship_id = request.GET.get('internship')
    student_id = request.GET.get('student')

    # Get all for selects
    companies = Company.objects.all().order_by('company_name')
    internships = Internship.objects.select_related('company').order_by('company__company_name', 'title')
    students = User.objects.filter(role='student').order_by('username')

    # Filter internships and students based on selections
    if company_id:
        internships = internships.filter(company_id=company_id)
        students = students.filter(
            student__internshipapplication__internship__company_id=company_id
        ).distinct()

    if internship_id:
        students = students.filter(
            student__internshipapplication__internship_id=internship_id
        ).distinct()

    selected_student = None
    evaluations_by_internship = {}

    if student_id:
        selected_student = get_object_or_404(User, id=student_id, role='student')

        # Get evaluations for this student
        evaluations = PerformanceEvaluation.objects.filter(
            application__student__user=selected_student
        ).select_related(
            'application__internship__company'
        ).order_by('application__internship__title')

        # Calculate final score
        for eval in evaluations:
            if eval.company_supervisor_score and eval.academic_supervisor_score:
                eval.final_score = (eval.company_supervisor_score + eval.academic_supervisor_score) / 2
            else:
                eval.final_score = None

        # Group by internship
        for eval in evaluations:
            internship = eval.application.internship
            if internship not in evaluations_by_internship:
                evaluations_by_internship[internship] = []
            evaluations_by_internship[internship].append(eval)

    # POST actions (if needed, e.g., delete evaluation)
    if request.method == 'POST' and selected_student:
        eval_id = request.POST.get('eval_id')

        if 'delete_evaluation' in request.POST:
            evaluation = PerformanceEvaluation.objects.get(id=eval_id)
            # Notify supervisors before deleting
            Notification.objects.create(
                user=evaluation.company_supervisor.user,
                message=f"The evaluation for {evaluation.student.user.username} has been deleted by admin."
            )
            Notification.objects.create(
                user=evaluation.academic_supervisor.user,
                message=f"The evaluation for {evaluation.student.user.username} has been deleted by admin."
            )
            # Notify admin
            Notification.objects.create(
                user=request.user,
                message=f"You deleted the evaluation for {evaluation.student.user.username}."
            )
            evaluation.delete()

        elif 'reset_company' in request.POST:
            eval_id = request.POST.get('reset_company')
            evaluation = get_object_or_404(PerformanceEvaluation, id=eval_id)
            # Reset company supervisor fields
            evaluation.company_supervisor_score = None
            evaluation.company_question_answers = None
            evaluation.company_supervisor_comment = None
            evaluation.company_supervisor_submitted_at = None
            evaluation.save()

            # Notify company supervisor
            Notification.objects.create(
                user=evaluation.company_supervisor.user,
                message=f"Your evaluation for {evaluation.student.user.username} has been reset by admin. Please submit your evaluation again."
            )

            # Notify admin
            Notification.objects.create(
                user=request.user,
                message=f"You reset the company evaluation for {evaluation.student.user.username}."
            )

        return redirect(f"{request.path}?company={company_id or ''}&internship={internship_id or ''}&student={student_id}")

    return render(
        request,
        'admin/admin_evaluations_manage.html',
        {
            'companies': companies,
            'internships': internships,
            'students': students,
            'selected_company': company_id,
            'selected_internship': internship_id,
            'selected_student': selected_student,
            'evaluations_by_internship': evaluations_by_internship,
        }
    )
def admin_add_internship(request):
    if request.method == 'POST':
        form = InternshipForm(request.POST)
        if form.is_valid():
            internship = form.save()
            # Notify admin
            Notification.objects.create(
                user=request.user,
                message=f"You added internship {internship.title} at {internship.company.company_name}."
            )
            return redirect('admin_internships_list')
    else:
        form = InternshipForm()

    return render(request, 'admin/admin_internships_form.html', {
        'form': form,
        'is_edit': False
    })


@login_required
@role_required(allowed_roles=['admin'])
def admin_edit_internship(request, internship_id):
    # Get the internship instance
    internship = get_object_or_404(Internship, pk=internship_id)

    if request.method == 'POST':
        form = InternshipForm(request.POST, instance=internship)
        if form.is_valid():
            internship = form.save()
            # Notify admin
            Notification.objects.create(
                user=request.user,
                message=f"You updated internship {internship.title} at {internship.company.company_name}."
            )
            return redirect('admin_internships_list')
    else:
        form = InternshipForm(instance=internship)

    return render(request, 'admin/admin_internships_form.html', {
        'form': form,
        'is_edit': True
    })



@login_required
@role_required(allowed_roles=['admin'])
def admin_delete_internship(request, internship_id):
    internship = get_object_or_404(Internship, id=internship_id)
    # Notify admin
    Notification.objects.create(
        user=request.user,
        message=f"You deleted internship {internship.title} at {internship.company.company_name}."
    )
    internship.delete()
    messages.success(request, f'Internship "{internship.title}" has been deleted.')
    return redirect('admin_internships_list')


#student manage profile and upload docs
@login_required
@role_required(allowed_roles=['student', 'company'])
def student_profile(request, student_id=None):
    # Determine the student to display
    if student_id:
        # Company supervisor viewing a specific student
        if request.user.role != 'company':
            return HttpResponseForbidden("Access denied.")
        
        company_supervisor = request.user.companysupervisor
        student = get_object_or_404(
            Student,
            id=student_id,
            internshipplacement__company_supervisor=company_supervisor,
            internshipplacement__status='Active'
        )
        is_owner = False  

    else:
        # Student viewing their own profile
        if request.user.role != 'student':
            return redirect('dashboard') 
        try:
            student = Student.objects.get(user=request.user)
        except Student.DoesNotExist:
            return render(request, 'student/profile.html', {
                'error': 'Your student profile has not been created yet. Please contact the administrator.',
                'is_owner': True
            })
        is_owner = True

    documents = Document.objects.filter(student=student)
    
    # Get the active placement for the student
    placement = InternshipPlacement.objects.filter(
        student=student,
        status='Active'
    ).first()

    return render(request, 'student/profile.html', {
        'student': student,
        'documents': documents,
        'placement': placement,
        'is_owner': is_owner,  
        'base_template': 'company/base.html' if not is_owner else 'student/base.html'
    })

@login_required
@role_required(allowed_roles=['student'])
def update_email(request):
    if request.method == 'POST':
        form = StudentProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('student_profile')
    else:
        form = StudentProfileForm(instance=request.user)

    return render(request, 'student/update_email.html', {
        'form': form,
        'current_email': request.user.email
    })

@login_required
@role_required(allowed_roles=['student'])
def upload_document(request):
    student = Student.objects.get(user=request.user)

    if request.method == 'POST':
        form = DocumentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.student = student
            doc.save()
            return redirect('student_profile')
    else:
        form = DocumentUploadForm()

    return render(request, 'student/upload_document.html', {
        'form': form
    })

def edit_document(request, doc_id):
    doc = get_object_or_404(Document, id=doc_id, student=request.user.student)
    if request.method == 'POST':
        form = DocumentUploadForm(request.POST, request.FILES, instance=doc)
        if form.is_valid():
            form.save()
            messages.success(request, 'Document updated successfully.')
            return redirect('student_profile')  
    else:
        form = DocumentUploadForm(instance=doc)
    return render(request, 'student/edit_document.html', {'form': form, 'doc': doc})

def delete_document(request, doc_id):
    doc = get_object_or_404(Document, id=doc_id, student=request.user.student)
    if request.method == 'POST':
        doc.delete()
        messages.success(request, 'Document deleted successfully.')
        return redirect('student_profile')  
    return render(request, 'student/delete_document.html', {'doc': doc})

#Internship detail
@login_required
@role_required(['student'])
def internship_list(request):
    student = request.user.student

    internships = Internship.objects.filter(status='Open')

    # Search
    query = request.GET.get('q')
    if query:
        internships = internships.filter(
            Q(title__icontains=query) |
            Q(company__company_name__icontains=query)
        )

    # Location filter
    location = request.GET.get('location')
    if location:
        internships = internships.filter(location=location)

    # Sorting
    sort = request.GET.get('sort')
    if sort == 'latest':
        internships = internships.order_by('-created_at')
    elif sort == 'oldest':
        internships = internships.order_by('created_at')

    internships = internships.annotate(
        has_applied=Exists(
            InternshipApplication.objects.filter(
                internship=OuterRef('pk'),
                student=student
            )
        )
    )

    # Unique locations for dropdown
    locations = Internship.objects.values_list('location', flat=True).distinct()

    context = {
        'internships': internships,
        'locations': locations
    }
    return render(request, 'student/internship_list.html', context)

#Apply internship
@login_required
@role_required(['student'])
def apply_internship(request, id):
    internship = get_object_or_404(Internship, id=id)
    student = Student.objects.get(user=request.user)

    #Block if student already placed
    if InternshipPlacement.objects.filter(student=student,status='Active').exists():
        return render(request, 'student/internship_apply.html', {
            'error': 'You have already been placed and cannot apply for new internships.'
            })

    #Block duplicate application
    if InternshipApplication.objects.filter(student=student, internship=internship).exists():
        return render(request, 'student/internship_apply.html', {
            'error': 'You have already applied for this internship.'
        })

    if request.method == 'POST':
        app_form = InternshipApplicationForm(request.POST)
        doc_form = DocumentUploadForm(request.POST, request.FILES)

        if app_form.is_valid() and doc_form.is_valid():
            application = InternshipApplication.objects.create(
                student=student,
                internship=internship,
                status='Pending'
            )

            document = doc_form.save(commit=False)
            document.student = student
            document.doc_type = 'Resume'
            document.save()

            company_supervisor = CompanySupervisor.objects.filter(
                company = internship.company,
                department=internship.department
            )

            for supervisor in company_supervisor:
                Notification.objects.create(
                    user=supervisor.user,
                    message=f"New application from {student.user.username}"
                )

            return render(request, 'student/internship_apply.html', {
                'success': 'Application submitted successfully!'
            })

    else:
        app_form = InternshipApplicationForm()
        doc_form = DocumentUploadForm()

    return render(request, 'student/internship_apply.html', {
        'app_form': app_form,
        'doc_form': doc_form,
        'internship': internship
    })

@login_required
@role_required(['company'])
def handle_application(request, app_id, action):
    company_supervisor = CompanySupervisor.objects.get(user=request.user)
    application = get_object_or_404(InternshipApplication, id=app_id)

    # Already handled
    if application.handled_by is not None:
        return redirect('company_dashboard')

    # Wrong department
    if application.internship.department != company_supervisor.department:
        return redirect('company_dashboard')

    if action == 'accept':
        application.status = 'Accepted'
        application.handled_by = company_supervisor
        application.save()

    elif action == 'reject':
        application.status = 'Rejected'
        application.handled_by = company_supervisor
        application.save()

    return redirect('company_dashboard')

@login_required
@role_required(['company'])
def supervisor_applications(request):
    company_supervisor = request.user.companysupervisor

    # Apply the 3-month limit 
    show_all_app = request.GET.get('filter') == 'all'

    applications = InternshipApplication.objects.filter(
        internship__company=company_supervisor.company,
        internship__department=company_supervisor.department
    ).select_related(
        'handled_by__user',
        'student__user'
    ).prefetch_related(  # fetch resumes
        Prefetch(
            'student__document_set',
            queryset=Document.objects.filter(doc_type='Resume'),
            to_attr='resumes'
        )
    ).order_by('-created_at')

    if not show_all_app:
        three_months_ago = timezone.now() - timedelta(days=90)
        applications = applications.filter(created_at__gte=three_months_ago)

    return render(request, 'company/applications.html', {
        'applications': applications,
        'show_all_app': show_all_app
    })


@login_required
def supervisor_decide(request, application_id):
    current_supervisor = request.user.companysupervisor
    application = InternshipApplication.objects.get(id=application_id)

    with transaction.atomic():
        application = InternshipApplication.objects.select_for_update().get(
            id=application_id
        )

        if application.handled_by:
            return redirect('supervisor_applications')

        if request.method == 'POST':
            decision = request.POST.get('decision')

            application.handled_by = current_supervisor

            if decision == 'offer':
                application.status = 'Offered'
                message = f"You received an internship offer for {application.internship.title} at {application.internship.company}"
            elif decision == 'reject':
                application.status = 'Rejected'
                message = f"Your application for {application.internship.title} was rejected"

            application.save()

        #Notify Student
        Notification.objects.create(
            user=application.student.user, 
            message=message
        )

        #Notify OTHER supervisors in the department
        other_supervisors = CompanySupervisor.objects.filter(
            department=current_supervisor.department
        ).exclude(id=current_supervisor.id)

        for supervisor in other_supervisors:
            Notification.objects.create(
                user=supervisor.user,
                message=f"Supervisor {request.user.username} has handled the application from {application.student.user.username}."
            )

        return redirect('supervisor_applications')
    
    return redirect('supervisor_applications')

@login_required
def student_offers(request):
    student = request.user.student

    applications = InternshipApplication.objects.filter(
        student=student
    ).select_related('internship', 'internship__company')

    return render(request, 'student/offers.html', {
        'applications': applications
    })

@login_required
def accept_offer(request, pk):
    application = get_object_or_404(InternshipApplication, pk=pk)

    if application.student != request.user.student:
        return redirect('student_offers')

    # Accept
    application.student_decision = 'Accepted'
    application.status = 'Accepted'
    application.save()

    # Create placement
    InternshipPlacement.objects.create(
        internship=application.internship,
        student=application.student,
        company_supervisor=application.handled_by,
        start_date=application.internship.start_date,
        end_date=application.internship.end_date,
        status='Active'
    )

    # Notify student about company supervisor assignment
    Notification.objects.create(
        user=application.student.user,
        message=f"You have been assigned to {application.handled_by.user.username} from {application.internship.company.company_name}."
    )

    # Notify company supervisor
    Notification.objects.create(
        user=application.handled_by.user,
        message=f"Student {application.student} has accepted your internship offer."
    )

    # Notify academic supervisor if exists
    if application.student.academic_supervisor:
        Notification.objects.create(
            user=application.student.academic_supervisor.user,
            message=f"{application.student.user.username} has accepted an internship "
                    f"at {application.internship.company.company_name}."
        )

    return redirect('student_offers')

@login_required
def reject_offer(request, pk):
    application = get_object_or_404(InternshipApplication, pk=pk)

    if application.student != request.user.student:
        return redirect('student_offers')

    application.student_decision = 'Rejected'
    application.status = 'Rejected'
    application.save()

    # Notify supervisor
    Notification.objects.create(
        user=application.handled_by.user,
        message=f"{application.student.user.username} has rejected your internship offer."
    )

    # Notify academic supervisor if exists
    if application.student.academic_supervisor:
        Notification.objects.create(
            user=application.student.academic_supervisor.user,
            message=f"{application.student.user.username} has rejected an internship offer."
        )

    return redirect('student_offers')

@login_required
def notifications(request):
    notes = Notification.objects.filter(user=request.user).order_by('-created_at')
    unread_count = Notification.objects.filter(user=request.user, is_read=False).count()

    return render(request, 'notifications/list.html', {
        'notifications': notes,
        'unread_count': unread_count
    })

@login_required
def mark_notification_read(request, pk):
    note = get_object_or_404(Notification, pk=pk, user=request.user)
    note.is_read = True
    note.save()
    return redirect('notifications')

#Weekly Logbook
@login_required
@role_required(['student'])
def logbook_list(request):
    student = get_object_or_404(Student, user=request.user)

    placement = InternshipPlacement.objects.filter(
        student=student,
        status='Active'
    ).first()

    if not placement:
        return render(request, 'student/logbook_list.html', {
            'error': 'You are not placed yet.'
        })

    application = InternshipApplication.objects.filter(
        student=student,
        internship=placement.internship,
        status='Accepted'
    ).first()

    logbooks = Logbook.objects.filter(student=student)

    submitted_weeks = {lb.week_no: lb for lb in logbooks}
    
    weeks_data = []
    for week in range(1, 13):
        weeks_data.append({
            'week': week,
            'logbook': submitted_weeks.get(week)
        })

    return render(request, 'student/logbook_list.html', {
        'weeks_data': weeks_data
    })

@login_required
@role_required(['student'])
def submit_logbook(request, week_no):
    student = get_object_or_404(Student, user=request.user)

    placement = InternshipPlacement.objects.filter(
        student=student,
        status='Active'
    ).first()

    if not placement:
        messages.error(request, "You are not placed.")
        return redirect('logbook_list')

    application = InternshipApplication.objects.filter(
        student=student,
        internship=placement.internship,
        status='Accepted'
    ).first()

    if not application:
        messages.error(request, "No accepted application found.")
        return redirect('logbook_list')

    # Deadline check
    start_date = placement.start_date
    deadline = start_date + timedelta(days=week_no * 7)

    if date.today() > deadline:
        return render(request, 'student/submit_logbook.html', {
            'error': 'Submission deadline has passed.',
            'week_no': week_no
        })

    # Prevent duplicate submission
    if Logbook.objects.filter(student=student, week_no=week_no).exists():
        messages.error(request, "Logbook already submitted.")
        return redirect('logbook_list')

    if request.method == 'POST':
        Logbook.objects.create(
            student=student,
            application=application,
            week_no=week_no,
            content=request.POST.get('content'),
            submitted_date=date.today(),
            status='Pending'
        )

        # Notify Supervisors
        if placement.company_supervisor:
            Notification.objects.create(
                user=placement.company_supervisor.user,
                message=f"{student.user.username} submitted logbook for Week {week_no}."
            )

        if student.academic_supervisor:
            Notification.objects.create(
                user=student.academic_supervisor.user,
                message=f"{student.user.username} submitted logbook for Week {week_no}."
            )

        messages.success(request, "Logbook submitted successfully.")
        return redirect('logbook_list')

    return render(request, 'student/submit_logbook.html', {
        'week_no': week_no
    })


@login_required
@role_required(['student'])
def edit_logbook(request, id):
    student = get_object_or_404(Student, user=request.user)
    logbook = get_object_or_404(Logbook, id=id, student=student)
    placement = InternshipPlacement.objects.filter(student=student, status='Active').first()

    if logbook.status != 'Pending':
        return render(request, 'student/logbook_edit.html', {
            'error': 'This logbook can no longer be edited.'
        })

    if request.method == 'POST':
        logbook.content = request.POST.get('content')
        logbook.updated_at = date.today()
        logbook.save()

        if placement and placement.company_supervisor:
            Notification.objects.create(
                user=placement.company_supervisor.user,
                message=f"{student.user.username} updated logbook for Week {logbook.week_no}."
            )

        if student.academic_supervisor:
            Notification.objects.create(
                user=student.academic_supervisor.user,
                message=f"{student.user.username} updated logbook for Week {logbook.week_no}."
            )

        messages.success(request, "Logbook updated.")
        return redirect('logbook_list')

    return render(request, 'student/logbook_edit.html', {
        'logbook': logbook
    })

#Company Supervisor View Logbook
@login_required
@role_required(['company'])
def company_logbook_review(request):
    supervisor = get_object_or_404(CompanySupervisor, user=request.user)
    show_all_log = request.GET.get('filter') == 'all'

    placements = InternshipPlacement.objects.filter(
        company_supervisor=supervisor,
        status='Active'
    )

    logbooks = Logbook.objects.filter(
        application__internship__in=[p.internship for p in placements]
    )

    if not show_all_log:
        three_months_ago = timezone.now() - timedelta(days=90)
        logbooks = logbooks.filter(created_at__gte=three_months_ago)

    return render(request, 'company/logbook_review.html', {
        'logbooks': logbooks,
        'show_all_log': show_all_log
    })

@login_required
@role_required(['company'])
def review_logbook(request, logbook_id):
    logbook = get_object_or_404(Logbook, id=logbook_id)

    if request.method == 'POST':
        review = request.POST.get('company_review')
        action = request.POST.get('action')

        # Save company review
        logbook.company_supervisor_notes = review

        if action == 'approve':
            logbook.company_approval = True
            logbook.status = 'Approved'
            logbook.approved_at = date.today()

            Notification.objects.create(
                user=logbook.student.user,
                message=f"Your logbook for Week {logbook.week_no} has been approved by {request.user.username}."
            )

            if logbook.student.academic_supervisor:
                Notification.objects.create(
                    user=logbook.student.academic_supervisor.user,
                    message=f"{logbook.student.user.username}'s logbook for Week {logbook.week_no} was approved by the Company Supervisor."
                )

        elif action == 'reject':
            logbook.company_approval = False
            logbook.status = 'Rejected'

            Notification.objects.create(
                user=logbook.student.user,
                message=f"Your logbook for Week {logbook.week_no} was rejected. Please review and resubmit."
            )

            if logbook.student.academic_supervisor:
                Notification.objects.create(
                    user=logbook.student.academic_supervisor.user,
                    message=f"{logbook.student.user.username}'s logbook for Week {logbook.week_no} was rejected by the Company Supervisor."
                )

        logbook.save()

        messages.success(request, "Logbook reviewed successfully.")
        return redirect('company_logbook_review')

#Academic Supervisor view approved logbook
@login_required
@role_required(['academic'])
def academic_logbook_review(request):
    supervisor = get_object_or_404(AcademicSupervisor, user=request.user)

    logbooks = Logbook.objects.filter(student__academic_supervisor=supervisor).order_by('student__user__username', 'week_no')

    return render(request, 'academic/logbook_review.html', {
        'logbooks': logbooks
    })

@login_required
@role_required(['academic'])
def academic_student_list(request):
    supervisor = request.user.academicsupervisor
    students = Student.objects.filter(academic_supervisor=supervisor)
    return render(request, 'academic/academic_student_list.html', {'students': students})

@login_required
def academic_student_list(request):
    supervisor = request.user.academicsupervisor

    students = Student.objects.filter(
        academic_supervisor=supervisor
    ).select_related('user')

    return render(
        request,
        'academic/academic_student_list.html',
        {'students': students}
    )

@login_required
def academic_performance_evaluation(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    placement = InternshipPlacement.objects.filter(student=student, status='Active').first()
    
    if request.method == 'POST':
        attendance_score = request.POST.get('attendance_score')
        punctuality_score = request.POST.get('punctuality_score')
        work_quality_score = request.POST.get('work_quality_score')
        overall_score = request.POST.get('overall_score')
        
        attendance_comment = request.POST.get('attendance_comment')
        punctuality_comment = request.POST.get('punctuality_comment')
        work_quality_comment = request.POST.get('work_quality_comment')
        overall_comment = request.POST.get('overall_comment')
        
        try:
            academic_supervisor = AcademicSupervisor.objects.get(user=request.user)
        except AcademicSupervisor.DoesNotExist:
            messages.error(request, 'You are not registered as an academic supervisor.')
            return redirect('academic_dashboard')
        
        if placement:
            # Get or create a dummy company supervisor (required by model)
            try:
                company_supervisor = placement.internship.company_supervisor
            except:
                # If no company supervisor exists, we need to handle this
                messages.error(request, 'No company supervisor assigned to this internship.')
                return redirect('academic_performance_evaluation', student_id=student_id)
            
            evaluation = PerformanceEvaluation.objects.create(
                student=student,
                academic_supervisor=academic_supervisor,
                application=placement.application,
                company_supervisor=company_supervisor
            )

            
            # Store evaluation data as JSON
            evaluation_data = {
                'attendance': {
                    'score': int(attendance_score) if attendance_score else None,
                    'comment': attendance_comment
                },
                'punctuality': {
                    'score': int(punctuality_score) if punctuality_score else None,
                    'comment': punctuality_comment
                },
                'work_quality': {
                    'score': int(work_quality_score) if work_quality_score else None,
                    'comment': work_quality_comment
                },
                'overall': {
                    'score': int(overall_score) if overall_score else None,
                    'comment': overall_comment
                }
            }
            
            evaluation.company_question_answers = evaluation_data
            
            # Calculate average score
            scores = [int(s) for s in [attendance_score, punctuality_score, work_quality_score, overall_score] if s]
            if scores:
                evaluation.academic_supervisor_score = sum(scores) // len(scores)
            
            evaluation.academic_supervisor_submitted_at = now()
            evaluation.save()
            
            messages.success(request, 'Evaluation submitted successfully!')
            return redirect('academic_performance_evaluation', student_id=student_id)
        else:
            messages.error(request, 'No active internship placement found for this student.')
            return redirect('academic_performance_evaluation', student_id=student_id)
    
    # Fetch all evaluations for this student, sorted by most recent first
    previous_evaluations = PerformanceEvaluation.objects.filter(
        student=student
    ).order_by('-academic_supervisor_submitted_at')
    
    return render(request, 'academic/academic_performance_evaluation.html', {
        'student': student,
        'placement': placement,
        'previous_evaluations': previous_evaluations
    })

@login_required
@role_required(['student'])
def student_attendance_summary(request):
    student = get_object_or_404(Student, user=request.user)

    placement = InternshipPlacement.objects.filter(
        student=student,
        status='Active'
    ).first()

    if not placement:
        return render(request, 'student/attendance.html', {
            'profile_missing': True,
            'attendances': [],
        })

    month = int(request.GET.get('month', datetime.today().month))
    year = int(request.GET.get('year', datetime.today().year))

    start_date = datetime(year, month, 1).date()
    # Calculate last day of month
    if month == 12:
        end_date = datetime(year + 1, 1, 1).date() - timedelta(days=1)
    else:
        end_date = datetime(year, month + 1, 1).date() - timedelta(days=1)
    
    today = date.today()
    last_day_to_check = min(end_date, today)

    # Fetch attendance in the month
    attendances = Attendance.objects.filter(
        placement=placement,
        date__range=[start_date, last_day_to_check]
    ).order_by('date')

    attended_dates = set(att.date for att in attendances if att.check_in)

    # Generate all dates up to today in the month
    all_dates_up_to_today = [start_date + timedelta(days=i) 
                             for i in range((last_day_to_check - start_date).days + 1)]

    # Count absent days
    total_days_present = len(attended_dates)
    total_days_absent = len([d for d in all_dates_up_to_today if d not in attended_dates])

    context = {
        'placement': placement,
        'attendances': attendances,
        'profile_missing': False,
        "months": range(1, 13),
        'month': month,
        'year': year,
        'total_days_present': total_days_present,
        'total_days_absent': total_days_absent,
        'start_date': start_date,
        'end_date': end_date,
        'today': today,
    }

    return render(request, 'student/attendance.html', context)


@login_required
def notifications(request):
    user_notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    
    # Mark all as read when viewing
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    
    context = {
        'notifications': user_notifications,
    }
    return render(request, 'notifications/list.html', context)


@login_required
def mark_notification_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.is_read = True
    notification.save()
    return redirect('notifications')


# Dummy student
supervisor = AcademicSupervisor.objects.first()
student_dummy = Student.objects.first()
student_dummy.academic_supervisor = supervisor
student_dummy.save()



