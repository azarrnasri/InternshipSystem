from django.contrib.auth.models import AbstractUser
from django.db import models

# Custom User Model
class User(AbstractUser):
    ROLE_CHOICES = [
        ('student', 'Student'),
        ('company', 'Company Supervisor'),
        ('academic', 'Academic Supervisor'),
        ('admin', 'Admin'),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, blank=True, null=True)
    def __str__(self):
        return self.username
    
# Academic Supervisor
class AcademicSupervisor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    department = models.CharField(max_length=100)

    def __str__(self):
        return self.user.username
    
# Student
class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    program = models.CharField(max_length=100)
    semester = models.CharField(max_length=20)
    academic_supervisor = models.ForeignKey(
        AcademicSupervisor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    def __str__(self):
        return self.user.username
    
# Company
class Company(models.Model):
    company_name = models.CharField(max_length=150)
    address = models.TextField()

    def __str__(self):
        return self.company_name
    
# Company Supervisor
class CompanySupervisor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)

    def __str__(self):
        return self.user.username
    
# Internship
class Internship(models.Model):
    STATUS_CHOICES = [
        ('Open', 'Open'),
        ('Closed', 'Closed'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    title = models.CharField(max_length=150)
    description = models.TextField()
    requirements = models.TextField(null=True, blank=True)
    location = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    total_slots = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.title
    
# Internship Application
class InternshipApplication(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Accepted', 'Accepted'),
        ('Rejected', 'Rejected'),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    internship = models.ForeignKey(Internship, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    applied_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('student', 'internship')
        
    def __str__(self):
        return f"{self.student} - {self.internship}"
    
# Internship Placement
class InternshipPlacement(models.Model):
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Completed', 'Completed'),
    ]

    internship = models.ForeignKey(Internship, on_delete=models.CASCADE)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    company_supervisor = models.ForeignKey(CompanySupervisor, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    assigned_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    updated_at = models.DateTimeField(null=True, blank=True)

# Attendance
class Attendance(models.Model):
    placement = models.ForeignKey(InternshipPlacement, on_delete=models.CASCADE)
    date = models.DateField()
    check_in = models.TimeField()
    check_out = models.TimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True, blank=True)

# Logbook
class Logbook(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    application = models.ForeignKey(InternshipApplication, on_delete=models.CASCADE)
    week_no = models.PositiveIntegerField()
    content = models.TextField()
    company_approval = models.BooleanField(null=True, blank=True)
    academic_supervisor_notes = models.TextField(null=True, blank=True)
    submitted_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)

# Performance Evaluation
class PerformanceEvaluation(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    company_supervisor = models.ForeignKey(CompanySupervisor, on_delete=models.CASCADE)
    academic_supervisor = models.ForeignKey(AcademicSupervisor, on_delete=models.CASCADE)
    application = models.ForeignKey(InternshipApplication, on_delete=models.CASCADE)
    company_supervisor_score = models.PositiveIntegerField()
    academic_supervisor_score = models.PositiveIntegerField()
    company_supervisor_comment = models.TextField(null=True, blank=True)
    academic_supervisor_comment = models.TextField(null=True, blank=True)
    company_supervisor_submitted_at = models.DateTimeField(null=True, blank=True)
    academic_supervisor_submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True, blank=True)

# Document
class Document(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    file = models.FileField(upload_to='documents/')
    doc_type = models.CharField(max_length=50)
    upload_date = models.DateTimeField(auto_now_add=True)