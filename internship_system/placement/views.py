
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db import transaction
from django.views.decorators.http import require_POST
from django.db.models import Q, Prefetch, Exists, OuterRef
from django.utils import timezone
from .decorators import role_required
from .forms import AdminUserForm, StudentForm, AcademicSupervisorForm, CompanySupervisorForm, StudentProfileForm, DocumentUploadForm, InternshipApplicationForm, InternshipForm
from django.utils.timezone import now
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from .models import (
    User,
    Student, 
    Logbook, 
    Attendance, 
    PerformanceEvaluation, 
    AcademicSupervisor,
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
        internship__company = company,
        #internship__department=company_supervisor.department,
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

    #5. Intern list (for table / navbar)
    interns = Student.objects.filter(
        internshipplacement__company_supervisor = company_supervisor,
        internshipplacement__status = 'Active'
    ).distinct()

    #6. Pending evaluation
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
            'interns': interns,
            'pending_evaluation': pending_evaluation,
            'profile_missing': False,
        }
    )

@login_required
@role_required(allowed_roles=['company'])
def interns_attendance(request):
    today = now().date()

    # Get company supervisor profile
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

    # Handle POST (Check-in / Check-out)
    if request.method == 'POST':
        placement_id = request.POST.get('placement_id')
        action = request.POST.get('action')

        placement = get_object_or_404(
            InternshipPlacement,
            id=placement_id,
            company_supervisor = company_supervisor
        )

        attendance, created = Attendance.objects.get_or_create(
            placement=placement,
            date=today,
            defaults={'check_in': now().time()}
        )

        if action == 'checkout' and attendance.check_out is None:
            attendance.check_out = now().time()
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

    evaluation_map = {}

    for placement in placements:
        evaluation_map[placement.id] = PerformanceEvaluation.objects.filter(
            application__student = placement.student,
            company_supervisor = company,
            company_supervisor_submitted_at__isnull=False
        ).exists()

    context = {
        'placements': placements,
        'evaluation_map': evaluation_map,
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

    #if placement.status != 'Completed':
    #    return render(request, 'Company/evaluation_locked.html')

    evaluation, created = PerformanceEvaluation.objects.get_or_create(
        student = placement.student,
        company_supervisor = placement.company_supervisor,
        academic_supervisor = placement.student.academic_supervisor,
        application=InternshipApplication.objects.filter(
            student = placement.student
        ).first()
    )

    if evaluation.company_supervisor_submitted_at:
        return render(request, 'company/evaluation_done.html')

    if request.method == 'POST':
        scores = [
            int(request.POST['q1']),
            int(request.POST['q2']),
            int(request.POST['q3']),
            int(request.POST['q4']),
            int(request.POST['q5']),
        ]

        evaluation.company_supervisor_score = sum(scores)
        evaluation.company_supervisor_comment = request.POST.get('comment')
        evaluation.company_supervisor_submitted_at = now()
        evaluation.save()

        return redirect('evaluation_list')

    return render(request, 'company/evaluation_form.html', {
        'placement': placement
    })

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

    return render(request, 'academic_dashboard.html')

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

@login_required
@role_required(allowed_roles=['admin'])
def admin(request):
    return render(request, 'admin/admin.html')

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

    user.delete()
    return redirect('admin_user_list')

@login_required
@role_required(allowed_roles=['admin'])
def admin_user_list(request):
    students = User.objects.filter(role='student').select_related('student')
    academics = User.objects.filter(role='academic').select_related('academicsupervisor')
    companies = User.objects.filter(role='company').select_related('companysupervisor')
    admins = User.objects.filter(role='admin')

    return render(request, 'admin/admin_user_list.html', {
        'students': students,
        'academics': academics,
        'companies': companies,
        'admins': admins,
    })

@login_required
@role_required(allowed_roles=['admin'])
def admin_company_list(request):
    companies = Company.objects.all()
    return render(request, 'admin/admin_company_list.html', {
        'companies': companies
    })


@login_required
@role_required(allowed_roles=['admin'])
def admin_add_company(request):
    if request.method == 'POST':
        company_name = request.POST.get('company_name')
        address = request.POST.get('address')

        if company_name and address:
            Company.objects.create(
                company_name=company_name,
                address=address
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

    company.delete()
    return redirect('admin_company_list')


@login_required
@role_required(allowed_roles=['admin'])
def admin_internships_list(request):
    internships = (
        Internship.objects
        .select_related('company')
        .order_by('company__company_name', 'title')
    )

    return render(
        request,
        'admin/admin_internships_list.html',
        {
            'internships': internships
        }
    )


@login_required
@role_required(allowed_roles=['admin'])
def admin_add_internship(request):
    if request.method == 'POST':
        form = InternshipForm(request.POST)
        if form.is_valid():
            form.save()
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
            form.save()
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
    internship.delete()
    messages.success(request, f'Internship "{internship.title}" has been deleted.')
    return redirect('admin_internships_list')


#student manage profile and upload docs
@login_required
@role_required(allowed_roles=['student'])
def student_profile(request):
    try:
        student = Student.objects.get(user=request.user)
    except Student.DoesNotExist:
        return render(request, 'student/profile.html', {
            'error': 'Your student profile has not been created yet. Please contact the administrator.'
        })

    documents = Document.objects.filter(student=student)

    return render(request, 'student/profile.html', {
        'student': student,
        'documents': documents
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

            supervisors = CompanySupervisor.objects.filter(department=internship.department)

            for supervisor in supervisors:
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
    supervisor = CompanySupervisor.objects.get(user=request.user)
    application = get_object_or_404(InternshipApplication, id=app_id)

    # Already handled
    if application.handled_by is not None:
        return redirect('company_dashboard')

    # Wrong department
    if application.internship.department != supervisor.department:
        return redirect('company_dashboard')

    if action == 'accept':
        application.status = 'Accepted'
        application.handled_by = supervisor
        application.save()

        # Notify student
        Notification.objects.create(
            user=application.student.user,
            message=f"You received an internship offer for {application.internship.title}"
        )

    elif action == 'reject':
        application.status = 'Rejected'
        application.handled_by = supervisor
        application.save()

        Notification.objects.create(
            user=application.student.user,
            message=f"Your application for {application.internship.title} was rejected"
        )

    return redirect('company_dashboard')

@login_required
@role_required(['company'])
def supervisor_applications(request):
    supervisor = request.user.companysupervisor

    applications = InternshipApplication.objects.filter(
        internship__department=supervisor.department,
        status='Pending'
    )

    return render(request, 'company/applications.html', {
        'applications': applications
    })


@login_required
def supervisor_decide(request, application_id):
    application = InternshipApplication.objects.get(id=application_id)

    if application.status != 'Pending':
        return HttpResponse("Already handled")

    if request.method == 'POST':
        decision = request.POST.get('decision')
        if decision == 'offer':
            # Assign the supervisor who clicked "Offer"
            if not application.handled_by:
                application.handled_by = request.user.companysupervisor
            application.status = 'Offered'
        elif decision == 'reject':
            application.status = 'Rejected'
        application.save()
        return redirect('supervisor_applications')
    
    return redirect('supervisor_applications')


@login_required
def student_accept_offer(request, application_id):
    application = InternshipApplication.objects.get(id=application_id)

    if application.student != request.user.student:
        return HttpResponseForbidden()

    application.student_decision = 'Accepted'
    application.status = 'Accepted'
    application.save()

    InternshipPlacement.objects.create(
        internship=application.internship,
        student=application.student,
        company_supervisor=application.handled_by,
        start_date=application.internship.start_date,
        end_date=application.internship.end_date,
        status='Active'
    )

@login_required
def student_offers(request):
    student = request.user.student

    offers = InternshipApplication.objects.filter(
        student=student,
        status='Offered',
        student_decision='Pending'
    )

    return render(request, 'student/offers.html', {
        'offers': offers
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

    # Notify company supervisor
    Notification.objects.create(
        user=application.handled_by.user,
        message=f"{application.student} accepted your internship offer."
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
        message=f"{application.student.user.username} rejected your internship offer."
    )

    # Notify academic supervisor if exists
    if application.student.academic_supervisor:
        Notification.objects.create(
            user=application.student.academic_supervisor.user,
            message=f"{application.student.user.username} rejected an internship offer."
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

