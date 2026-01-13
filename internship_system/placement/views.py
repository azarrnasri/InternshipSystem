# Create your views here.
from django.shortcuts import render, redirect, get_object_or_404, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db import transaction
from django.views.decorators.http import require_POST
from django.db.models import Q
from django.utils import timezone
from .decorators import role_required
from .forms import AdminUserForm, StudentForm, AcademicSupervisorForm, CompanySupervisorForm, StudentProfileForm, DocumentUploadForm, InternshipApplicationForm
from django.utils.timezone import now
from django.db.models import Prefetch
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
    InternshipPlacement
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

    return render(
        request,
        'company/dashboard.html',
        {
            'total_interns': total_interns,
            'pending_applications': pending_applications,
            'pending_logbooks': pending_logbooks,
            'attendance_not_marked': attendance_not_marked,
            'interns': interns,
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
        company.company_name = request.POST.get('company_name')
        company.address = request.POST.get('address')
        company.save()
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
        return render(request, 'student/apply_internship.html', {
            'error': 'You have already been placed and cannot apply for new internships.'
            })

    #Block duplicate application
    if InternshipApplication.objects.filter(student=student, internship=internship).exists():
        return render(request, 'student/apply_internship.html', {
            'error': 'You have already applied for this internship.'
        })

    if request.method == 'POST':
        app_form = InternshipApplicationForm(request.POST)
        doc_form = DocumentUploadForm(request.POST, request.FILES)

        if app_form.is_valid() and doc_form.is_valid():
            application = InternshipApplication.objects.create(
                student=student,
                internship=internship
            )

            document = doc_form.save(commit=False)
            document.student = student
            document.doc_type = 'Resume'
            document.save()

            return render(request, 'student/apply_internship.html', {
                'success': 'Application submitted successfully!'
            })

    else:
        app_form = InternshipApplicationForm()
        doc_form = DocumentUploadForm()

    return render(request, 'student/apply_internship.html', {
        'app_form': app_form,
        'doc_form': doc_form,
        'internship': internship
    })


