# Create your views here.
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .decorators import role_required
from .models import Student, Document
from .forms import StudentProfileForm, DocumentUploadForm

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
    return render(request, 'academic_dashboard.html')

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

    if request.method == 'POST':
        student_form = StudentProfileForm(request.POST, instance=request.user)
        doc_form = DocumentUploadForm(request.POST, request.FILES)

        if student_form.is_valid():
            student_form.save()

        if doc_form.is_valid():
            doc = doc_form.save(commit=False)
            doc.student = student
            doc.save()

        return redirect('student_profile')

    else:
        student_form = StudentProfileForm(instance=request.user)
        doc_form = DocumentUploadForm()

    return render(request, 'student/profile.html', {
        'student': student,
        'student_form': student_form,
        'doc_form': doc_form,
        'documents': documents
    })
