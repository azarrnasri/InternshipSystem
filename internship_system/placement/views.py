# Create your views here.
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from .decorators import role_required
from .forms import AdminUserForm, StudentForm, AcademicSupervisorForm, CompanySupervisorForm
from .models import User, Student, AcademicSupervisor, CompanySupervisor, Company
from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from django.views.decorators.http import require_POST



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
    return render(request, 'company_dashboard.html')

@login_required
@role_required(allowed_roles=['academic'])
def academic_dashboard(request):
    return render(request, 'academic_dashboard.html')

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