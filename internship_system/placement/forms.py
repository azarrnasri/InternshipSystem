from django import forms
from .models import User, Student, AcademicSupervisor, CompanySupervisor, InternshipApplication, Document
from django.contrib.auth import get_user_model

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
        fields = ['department']

class CompanySupervisorForm(forms.ModelForm):
    class Meta:
        model = CompanySupervisor
        fields = ['company']

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
        if file.content_type not in ALLOWED_TYPES:
            raise forms.ValidationError("Only PDF or Word documents are allowed.")
        return file
