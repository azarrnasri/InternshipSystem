from django import forms
from .models import User, Student, AcademicSupervisor, CompanySupervisor

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