from .models import (
    CompanySupervisor,
    InternshipPlacement,
    Notification
)

def company_interns(request):
    if not request.user.is_authenticated:
        return {}

    try:
        company_supervisor = request.user.companysupervisor
    except CompanySupervisor.DoesNotExist:
        return {}

    interns = InternshipPlacement.objects.filter(
        company_supervisor=company_supervisor,
        status="Active"
    ).select_related("student__user").distinct()

    interns = [p.student for p in interns]

    return {
        "interns": interns
    }

def company_notifications(request):
    if not request.user.is_authenticated:
        return {}

    unread_count = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).count()

    return {
        "unread_count": unread_count,
    } 