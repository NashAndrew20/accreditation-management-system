from datetime import timedelta

from django.db.models import Count
from django.utils import timezone
from django.utils.timesince import timesince
from django.views.generic import TemplateView

from accreditation.models import AccreditationCycle, AccreditationLevel, EvidenceRequirement, EvidenceSubmission
from core.access import accessible_submissions, active_assignment
from core.models import AuditLog
from core.mixins import ApprovedUserRequiredMixin

from .charting import build_line_chart


COMPLETED_STATUSES = {EvidenceSubmission.COMPLIED, EvidenceSubmission.CLOSED}
ACTIVE_REVIEW_STATUSES = {
    EvidenceSubmission.UNDER_DEAN_REVIEW,
    EvidenceSubmission.UNDER_AREA_CHAIR_REVIEW,
    EvidenceSubmission.UNDER_QA_REVIEW,
}


class DashboardView(ApprovedUserRequiredMixin, TemplateView):
    template_name = 'dashboard/index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        cycle = AccreditationCycle.objects.filter(is_active=True).first()
        assignment = active_assignment(user)
        submissions = accessible_submissions(user).select_related('requirement', 'requirement__area', 'department', 'program_head')
        total = submissions.count()
        complied = submissions.filter(status__in=COMPLETED_STATUSES).count()
        pending = submissions.filter(status__in=ACTIVE_REVIEW_STATUSES).count()
        revisions = submissions.filter(status=EvidenceSubmission.NEEDS_REVISION).count()
        readiness = round(complied * 100 / total) if total else 0

        levels = AccreditationLevel.objects.filter(cycle=cycle).prefetch_related('areas') if cycle else AccreditationLevel.objects.none()
        active_level = levels.filter(code='I').first() or levels.first()
        area_readiness = []
        highest_gap = None
        if active_level:
            for area in active_level.areas.all():
                requirement_count = EvidenceRequirement.objects.filter(area=area).count()
                completed_count = submissions.filter(
                    requirement__area=area,
                    status__in=COMPLETED_STATUSES,
                ).count()
                value = round(completed_count * 100 / requirement_count) if requirement_count else 0
                area_readiness.append({
                    'code': area.code,
                    'value': value,
                    'tone': 'green' if value >= 80 else 'gold' if value >= 50 else 'maroon',
                })
                gap = (100 - value, area)
                if highest_gap is None or gap[0] > highest_gap[0]:
                    highest_gap = gap

        if highest_gap:
            alert_area = highest_gap[1]
            missing_departments = submissions.filter(
                requirement__area=alert_area,
                status=EvidenceSubmission.DRAFT,
            ).values('department_id').distinct().count()
            alert = {
                'area_code': alert_area.code,
                'area_name': alert_area.name,
                'readiness_gap': highest_gap[0],
                'days_left': None,
                'departments_missing': missing_departments,
                'message': f'has a {highest_gap[0]}% readiness gap. {missing_departments} departments still have draft or missing evidence.' if missing_departments else f'has a {highest_gap[0]}% readiness gap. Review the outstanding requirements before the next internal checkpoint.',
            }
        else:
            alert = {
                'area_code': 'No active area',
                'area_name': 'Evidence readiness',
                'readiness_gap': 0,
                'days_left': None,
                'departments_missing': 0,
                'message': 'Activate an accreditation cycle and configure evidence requirements to begin monitoring readiness.',
            }

        context['cycle'] = {
            'office': assignment.department.name if assignment else 'Quality Assurance Office',
            'academic_year': cycle.academic_year if cycle else 'No active cycle',
            'program': cycle.name if cycle else 'Accreditation Cycle',
        }
        context['alert'] = alert
        context['stats'] = [
            {
                'label': 'Total Submissions',
                'value': total,
                'note': f'{submissions.filter(created_at__gte=timezone.now() - timedelta(days=7)).count()} this week',
                'icon': 'file',
                'tone': 'rose',
            },
            {
                'label': 'Complied',
                'value': complied,
                'note': f'{readiness}% compliance rate',
                'icon': 'check',
                'tone': 'green',
            },
            {
                'label': 'Pending Review',
                'value': pending,
                'note': 'Awaiting assigned reviewer',
                'icon': 'clock',
                'tone': 'gold',
            },
            {
                'label': 'Needs Revision',
                'value': revisions,
                'note': 'Returned to Program Heads',
                'icon': 'alert',
                'tone': 'red',
            },
        ]

        months = []
        submitted_values = []
        complied_values = []
        revision_values = []
        now = timezone.now()
        for offset in range(5, -1, -1):
            month_start = (now.replace(day=1) - timedelta(days=offset * 31)).replace(day=1)
            next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
            months.append(month_start.strftime('%b'))
            month_submissions = submissions.filter(created_at__gte=month_start, created_at__lt=next_month)
            submitted_values.append(month_submissions.count())
            complied_values.append(month_submissions.filter(status__in=COMPLETED_STATUSES).count())
            revision_values.append(month_submissions.filter(status=EvidenceSubmission.NEEDS_REVISION).count())
        chart_max = max([1, *submitted_values, *complied_values, *revision_values])
        raw_series = [
            {'name': 'Submitted', 'color': 'maroon', 'values': submitted_values},
            {'name': 'Complied', 'color': 'green', 'values': complied_values},
            {'name': 'Revision', 'color': 'gold', 'values': revision_values},
        ]
        context['trend'] = {
            'range_label': f'{months[0]} – {months[-1]} {now.year}',
            'y_ticks': [0, max(1, chart_max // 4), max(1, chart_max // 2), max(1, (chart_max * 3) // 4), chart_max],
            'chart': build_line_chart(months, raw_series, max_value=chart_max),
        }
        context['area_readiness'] = {
            'sublabel': f'{active_level.name if active_level else "No active level"} · Current access scope',
            'areas': area_readiness,
        }

        recent_activity = []
        audit_events = AuditLog.objects.filter(submission__in=submissions).select_related(
            'actor', 'submission__requirement', 'submission__requirement__area'
        )[:5]
        for event in audit_events:
            actor = event.actor.get_full_name() if event.actor else 'System'
            action_labels = {
                'SUBMITTED': 'submitted evidence for',
                'DRAFT_SAVED': 'saved a draft for',
                'APPROVED': 'approved',
                'REQUEST_REVISION': 'requested revision on',
                'COMPLIED': 'marked complied',
                'CLOSED': 'closed',
                'NON_COMPLIED': 'marked non-complied',
            }
            recent_activity.append({
                'tone': 'green' if event.action in {'APPROVED', 'COMPLIED', 'CLOSED'} else 'maroon' if event.action in {'REQUEST_REVISION', 'NON_COMPLIED'} else 'blue',
                'actor': actor or event.actor.username,
                'action': action_labels.get(event.action, event.action.replace('_', ' ').lower()),
                'target': event.submission.requirement.code if event.submission else event.object_type,
                'time_ago': f'{timesince(event.created_at)} ago',
            })

        context['recent_activity'] = recent_activity
        context['upcoming_deadlines'] = []
        context['quick_actions'] = ['Submit Evidence', 'Review Queue', 'Upload Document', 'View Reports']
        context['hide_topbar_title'] = True
        return context
