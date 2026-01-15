from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User, Student, AcademicSupervisor, CompanySupervisor, Company


@receiver(post_save, sender=User)
def create_role_profile(sender, instance, created, **kwargs):
    if not created:
        return

    if instance.role == 'student':
        Student.objects.get_or_create(
            user=instance,
            defaults={'program': '', 'semester': ''}
        )

    elif instance.role == 'academic':
        AcademicSupervisor.objects.get_or_create(
            user=instance,
            defaults={'faculty': ''}
        )

    elif instance.role == 'company':
        default_company = Company.objects.get(company_name="Unassigned Company")
        CompanySupervisor.objects.get_or_create(
            user=instance,
            defaults={'company': default_company}
        )


