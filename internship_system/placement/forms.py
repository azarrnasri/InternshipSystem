from django import forms
from .models import User, Student, AcademicSupervisor, CompanySupervisor, InternshipApplication, Document, Internship, Company, Department, InternshipPlacement
from django.contrib.auth import get_user_model
from django import forms


User = get_user_model()

ALLOWED_TYPES = ['application/pdf', 'application/msword',
                 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']

class AdminUserForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput,
        required=False
    )
    class Meta:
        model = User
        fields = [
            'username', 'email', 'first_name', 'last_name',
            'role', 'is_active', 'password']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance.pk:
            self.fields['role'].disabled = True

class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = ['program', 'semester', 'academic_supervisor']

class AcademicSupervisorForm(forms.ModelForm):
    class Meta:
        model = AcademicSupervisor
        fields = ['faculty']



# forms.py

class InternshipForm(forms.ModelForm):
    class Meta:
        model = Internship
        fields = [
            'company',
            'department',
            'title',
            'description',
            'requirements',
            'location',
            'start_date',
            'end_date',
            'total_slots',
            'status',
        ]
        widgets = {
            'company': forms.Select(attrs={'class': 'form-control'}),
            'department': forms.Select(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Internship title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'requirements': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'total_slots': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Default: no departments until a company is chosen
        self.fields['department'].queryset = Department.objects.none()

        # If editing existing internship or company is pre-selected
        if 'company' in self.data:
            try:
                company_id = int(self.data.get('company'))
                self.fields['department'].queryset = Department.objects.filter(company_id=company_id)
            except (ValueError, TypeError):
                pass  # invalid input; leave empty
        elif self.instance.pk and self.instance.company:
            self.fields['department'].queryset = Department.objects.filter(company=self.instance.company)


from django import forms
from .models import InternshipPlacement, CompanySupervisor


class InternshipPlacementForm(forms.ModelForm):
    class Meta:
        model = InternshipPlacement
        fields = [
            'student',
            'internship',
            'company_supervisor',
            'start_date',
            'end_date',
            'status',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        placement = self.instance

        if placement.pk:
            self.fields['student'].disabled = True
            self.fields['internship'].disabled = True

            internship = placement.internship
            company = internship.company
            department = internship.department

            qs = CompanySupervisor.objects.filter(company=company)
            if department:
                qs = qs.filter(department=department)

            self.fields['company_supervisor'].queryset = qs
        else:
            self.fields['company_supervisor'].queryset = CompanySupervisor.objects.none()

    def clean_student(self):
        if self.instance.pk:
            return self.instance.student
        return self.cleaned_data['student']

    def clean_internship(self):
        if self.instance.pk:
            return self.instance.internship
        return self.cleaned_data['internship']






class CompanySupervisorForm(forms.ModelForm):
    class Meta:
        model = CompanySupervisor
        fields = ['company', 'department']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Default: no departments until company is chosen
        self.fields['department'].queryset = Department.objects.none()

        # Editing existing supervisor
        if self.instance.pk and self.instance.company:
            self.fields['department'].queryset = (
                Department.objects.filter(company=self.instance.company)
            )

        # Company selected in POST (Add form)
        elif 'company' in self.data:
            try:
                company_id = int(self.data.get('company'))
                self.fields['department'].queryset = (
                    Department.objects.filter(company_id=company_id)
                )
            except (ValueError, TypeError):
                pass


class InternshipApplicationForm(forms.ModelForm):
    class Meta:
        model = InternshipApplication
        fields = []  # no editable fields

class StudentProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['email']


class DocumentUploadForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ['file']

    def clean_file(self):
        file = self.cleaned_data.get('file')

        if not file:
            return file
        
        if hasattr(file, 'content_type'):
            if file.content_type not in ALLOWED_TYPES:
                raise forms.ValidationError("Invalid file type")

        return file
    
        
