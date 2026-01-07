from django import forms
from django.contrib.auth import get_user_model
from .models import InternshipApplication, Document

User = get_user_model()

ALLOWED_TYPES = ['application/pdf', 'application/msword',
                 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']

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
