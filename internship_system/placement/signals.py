from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import User, Student, AcademicSupervisor, CompanySupervisor, Company, Internship, InternshipApplication, InternshipPlacement, Logbook, PerformanceEvaluation, Notification, Document


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

    # Notify admins of new user registration
    admins = User.objects.filter(role='admin')
    for admin in admins:
        Notification.objects.create(
            user=admin,
            message=f"New {instance.role} user registered: {instance.username} ({instance.email})"
        )


@receiver(post_save, sender=Company)
def notify_new_company(sender, instance, created, **kwargs):
    if not created:
        return

    admins = User.objects.filter(role='admin')
    for admin in admins:
        Notification.objects.create(
            user=admin,
            message=f"New company registered: {instance.company_name} at {instance.address}"
        )


@receiver(post_save, sender=Internship)
def notify_new_internship(sender, instance, created, **kwargs):
    if not created:
        return

    admins = User.objects.filter(role='admin')
    for admin in admins:
        Notification.objects.create(
            user=admin,
            message=f"New internship posted: '{instance.title}' by {instance.company.company_name}"
        )


@receiver(post_save, sender=InternshipApplication)
def notify_new_application(sender, instance, created, **kwargs):
    if not created:
        return

    admins = User.objects.filter(role='admin')
    for admin in admins:
        Notification.objects.create(
            user=admin,
            message=f"New internship application: {instance.student.user.username} applied for '{instance.internship.title}'"
        )


@receiver(post_save, sender=InternshipApplication)
def notify_application_status_change(sender, instance, created, **kwargs):
    if created:
        # New application - already handled above
        return

    # Check if status changed
    if hasattr(instance, '_original_status'):
        if instance._original_status != instance.status:
            admins = User.objects.filter(role='admin')
            status_messages = {
                'Accepted': f"Application accepted: {instance.student.user.username}'s application for '{instance.internship.title}' was accepted",
                'Rejected': f"Application rejected: {instance.student.user.username}'s application for '{instance.internship.title}' was rejected",
                'Offered': f"Offer made: {instance.student.user.username} received an offer for '{instance.internship.title}'"
            }
            if instance.status in status_messages:
                for admin in admins:
                    Notification.objects.create(
                        user=admin,
                        message=status_messages[instance.status]
                    )

    # Check if handled_by changed (supervisor assigned)
    if hasattr(instance, '_original_handled_by'):
        if instance._original_handled_by != instance.handled_by and instance.handled_by:
            admins = User.objects.filter(role='admin')
            for admin in admins:
                Notification.objects.create(
                    user=admin,
                    message=f"Supervisor assigned: {instance.handled_by.user.username} assigned to review {instance.student.user.username}'s application for '{instance.internship.title}'"
                )


@receiver(post_save, sender=Logbook)
def notify_logbook_status_change(sender, instance, created, **kwargs):
    if created:
        # New logbook - already handled above
        return

    # Check if status changed
    if hasattr(instance, '_original_status'):
        if instance._original_status != instance.status:
            admins = User.objects.filter(role='admin')
            status_messages = {
                'Approved': f"Logbook approved: Week {instance.week_no} logbook by {instance.student.user.username} was approved",
                'Rejected': f"Logbook rejected: Week {instance.week_no} logbook by {instance.student.user.username} was rejected"
            }
            if instance.status in status_messages:
                for admin in admins:
                    Notification.objects.create(
                        user=admin,
                        message=status_messages[instance.status]
                    )


@receiver(post_save, sender=InternshipPlacement)
def notify_new_placement(sender, instance, created, **kwargs):
    if not created:
        return

    admins = User.objects.filter(role='admin')
    for admin in admins:
        Notification.objects.create(
            user=admin,
            message=f"New internship placement: {instance.student.user.username} placed at {instance.company_supervisor.company.company_name}"
        )


@receiver(post_save, sender=Logbook)
def notify_new_logbook(sender, instance, created, **kwargs):
    if not created:
        return

    admins = User.objects.filter(role='admin')
    for admin in admins:
        Notification.objects.create(
            user=admin,
            message=f"New logbook submitted: Week {instance.week_no} by {instance.student.user.username}"
        )


@receiver(post_save, sender=PerformanceEvaluation)
def notify_evaluation_submitted(sender, instance, created, **kwargs):
    if not created:
        return

    admins = User.objects.filter(role='admin')
    for admin in admins:
        Notification.objects.create(
            user=admin,
            message=f"Performance evaluation submitted for {instance.student.user.username} by {instance.company_supervisor.user.username}"
        )


@receiver(post_save, sender=Document)
def notify_document_upload(sender, instance, created, **kwargs):
    if not created:
        return

    admins = User.objects.filter(role='admin')
    for admin in admins:
        Notification.objects.create(
            user=admin,
            message=f"Document uploaded: {instance.student.user.username} uploaded a {instance.doc_type} document"
        )
def store_original_application_status(sender, instance, **kwargs):
    if instance.pk:
        try:
            original = InternshipApplication.objects.get(pk=instance.pk)
            instance._original_status = original.status
            instance._original_handled_by = original.handled_by
        except InternshipApplication.DoesNotExist:
            instance._original_status = None
            instance._original_handled_by = None
    else:
        instance._original_status = None
        instance._original_handled_by = None


@receiver(pre_save, sender=Logbook)
def store_original_logbook_status(sender, instance, **kwargs):
    if instance.pk:
        try:
            original = Logbook.objects.get(pk=instance.pk)
            instance._original_status = original.status
        except Logbook.DoesNotExist:
            instance._original_status = None
    else:
        instance._original_status = None


