import json
import logging
import math
from datetime import timedelta

from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.generic import TemplateView, View

from .aira import ask

from accreditation.constants import ACTIVE_REVIEW_STATUSES, COMPLETED_STATUSES
from accreditation.models import AccreditationCycle, AccreditationLevel, EvidenceRequirement, EvidenceSubmission
from core.access import accessible_submissions, department_scope_ids
from core.mixins import ApprovedUserRequiredMixin
from core.models import AuditLog, Department
from core.rate_limit import allow_aira_request

from .pdf_export import build_report_pdf


logger = logging.getLogger(__name__)


def _points(values, max_value=36):
    max_value = max(float(max_value), 1)
    x_values = [30, 120, 210, 300, 390, 480]
    return ' '.join(f'{x},{220 - round(min(value, max_value) / max_value * 172)}' for x, value in zip(x_values, values))


def _point_data(values, labels, max_value=36):
    max_value = max(float(max_value), 1)
    x_values = [30, 120, 210, 300, 390, 480]
    return [
        {
            'x': x,
            'y': 220 - round(min(value, max_value) / max_value * 172),
            'label': label,
            'value': value,
        }
        for x, value, label in zip(x_values, values, labels)
    ]


def build_reports_context(user):
    """Build the live report data shared by the HTML page and PDF export."""
    cycle = AccreditationCycle.objects.filter(is_active=True).first()
    submissions = accessible_submissions(user)
    total = submissions.count()
    completed = submissions.filter(status__in=COMPLETED_STATUSES).count()
    revisions = submissions.filter(status=EvidenceSubmission.NEEDS_REVISION).count()
    pending = submissions.filter(status__in=ACTIVE_REVIEW_STATUSES).count()
    readiness = round(completed * 100 / total, 1) if total else 0
    compliance = round(completed * 100 / total, 1) if total else 0

    departments = []
    for department in Department.objects.filter(is_active=True, kind=Department.DEPARTMENT).order_by('name'):
        scoped = submissions.filter(department_id__in=department_scope_ids(department))
        submitted = scoped.exclude(status=EvidenceSubmission.DRAFT).count()
        compiled = scoped.filter(status__in=COMPLETED_STATUSES).count()
        if not submitted and not scoped.exists():
            continue
        rate = round(compiled * 100 / submitted) if submitted else 0
        departments.append({
            'name': department.name,
            'submitted': submitted,
            'compiled': compiled,
            'compliance': rate,
            'status': 'On Track' if rate >= 80 else 'At Risk' if rate >= 50 else 'Critical',
            'tone': 'green' if rate >= 80 else 'gold' if rate >= 50 else 'rose',
        })

    level = AccreditationLevel.objects.filter(cycle=cycle).filter(code='I').first() if cycle else None
    radar_areas = []
    if level:
        for area in level.areas.all():
            required = EvidenceRequirement.objects.filter(area=area).count()
            done = submissions.filter(requirement__area=area, status__in=COMPLETED_STATUSES).count()
            radar_areas.append({
                'code': area.code,
                'name': area.name,
                'value': round(done * 100 / required) if required else 0,
            })
    radar_areas += [
        {'code': f'Area {index + 1}', 'name': 'Not configured', 'value': 0}
        for index in range(11 - len(radar_areas))
    ]
    radar_areas = radar_areas[:11]
    radar_values = [area['value'] for area in radar_areas]
    radar_points = ' '.join(
        f'{130 + round(105 * value / 100 * math.cos(2 * math.pi * index / 11 - math.pi / 2)):.0f},{125 + round(105 * value / 100 * math.sin(2 * math.pi * index / 11 - math.pi / 2)):.0f}'
        for index, value in enumerate(radar_values)
    )
    for index, area in enumerate(radar_areas):
        area['x'] = 130 + round(105 * area['value'] / 100 * math.cos(2 * math.pi * index / 11 - math.pi / 2))
        area['y'] = 125 + round(105 * area['value'] / 100 * math.sin(2 * math.pi * index / 11 - math.pi / 2))

    recent = timezone.now()
    weekly_submitted = []
    weekly_revisions = []
    weekly_labels = []
    for week in range(6, 0, -1):
        start = recent - timedelta(days=week * 7)
        end = start + timedelta(days=7)
        weekly_labels.append(start.strftime('%b %d'))
        weekly_submitted.append(submissions.filter(created_at__gte=start, created_at__lt=end).count())
        weekly_revisions.append(submissions.filter(
            reviews__created_at__gte=start,
            reviews__created_at__lt=end,
            reviews__decision='REQUEST_REVISION',
        ).distinct().count())

    status_summary = [
        {'label': label, 'count': submissions.filter(status=status).count()}
        for status, label in EvidenceSubmission.STATUS_CHOICES
    ]
    return {
        'cycle': cycle,
        'report_metrics': {
            'readiness': readiness,
            'total': total,
            'completed': completed,
            'compliance': compliance,
            'revisions': revisions,
            'pending': pending,
        },
        'insights': [
            {
                'message': f'{readiness}% of visible evidence is complied across the current access scope.',
                'tone': 'green' if readiness >= 80 else 'gold',
                'icon': 'trend-up',
            },
            {
                'message': f'{pending} evidence items are currently waiting for an assigned internal reviewer.',
                'tone': 'gold',
                'icon': 'clock',
            },
            {
                'message': f'{revisions} evidence items are in revision and have been returned to their Program Heads.',
                'tone': 'rose' if revisions else 'green',
                'icon': 'alert' if revisions else 'check',
            },
        ],
        'kpis': [
            {'value': f'{readiness}%', 'label': 'Overall Readiness', 'delta': f'{total} visible submissions', 'tone': 'green' if readiness >= 80 else 'gold'},
            {'value': total, 'label': 'Total Submissions', 'delta': f'{pending} pending review', 'tone': 'green'},
            {'value': f'{compliance}%', 'label': 'Compliance Rate', 'delta': f'{completed} complied', 'tone': 'green' if compliance >= 80 else 'gold'},
            {'value': revisions, 'label': 'Needs Revision', 'delta': 'Returned for correction', 'tone': 'rose' if revisions else 'green'},
        ],
        'departments': departments,
        'radar_points': radar_points,
        'radar_areas': radar_areas,
        'trend_approval_points': _points(weekly_submitted),
        'trend_revision_points': _points(weekly_revisions),
        'trend_approval_data': _point_data(weekly_submitted, weekly_labels),
        'trend_revision_data': _point_data(weekly_revisions, weekly_labels),
        'status_summary': status_summary,
    }


class ReportsMonitoringView(ApprovedUserRequiredMixin, TemplateView):
    template_name = 'intelligence/reports_monitoring.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(build_reports_context(self.request.user))
        context['page_title'] = 'Reports & Monitoring'
        return context


class ReportsMonitoringExportView(ApprovedUserRequiredMixin, View):
    """Download the same live report data as a real PDF document."""

    def get(self, request, *args, **kwargs):
        report_context = build_reports_context(request.user)
        pdf = build_report_pdf(report_context)
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="jmcfi-ams-report.pdf"'
        return response


class SmartCompanionView(ApprovedUserRequiredMixin, TemplateView):
    template_name = 'intelligence/smart_companion.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'page_title': 'Smart Companion',
            'hide_topbar_title': True,
            'hide_aira_global': True,
        })
        return context


class AiraAskView(ApprovedUserRequiredMixin, View):
    """AJAX endpoint backing the Smart Companion chat.

    Every reply is derived from the authenticated user's authorized AMS
    records via ``intelligence.aira.ask``. The endpoint performs no external
    AI calls and returns only the advisory message, source label, and
    suggestion prompts.
    """

    MAX_QUESTION_LENGTH = 500
    MAX_REQUEST_BODY_BYTES = 4096

    def _extract_question(self, request):
        question = ''
        if request.content_type and request.content_type.startswith('application/json'):
            try:
                payload = json.loads(request.body or b'{}')
            except (ValueError, TypeError):
                payload = {}
            question = payload.get('question', '')
        else:
            question = request.POST.get('question', '')
        if not isinstance(question, str):
            return ''
        return question.strip()[: self.MAX_QUESTION_LENGTH]

    def post(self, request, *args, **kwargs):
        if not request.body or len(request.body) > self.MAX_REQUEST_BODY_BYTES:
            return JsonResponse(
                {'error': 'Request is empty or too large.'},
                status=413,
            )
        question = self._extract_question(request)
        if not question:
            return JsonResponse(
                {'error': 'Please provide a question.'},
                status=400,
            )
        try:
            allowed = allow_aira_request(request.user)
        except Exception:
            # A rate-limiter outage must not silently remove the server-side
            # protection. Return a safe, retryable failure instead.
            logger.exception('AIRA rate-limit check failed for user %s', request.user.pk)
            self._audit_error(request)
            return JsonResponse(
                {'error': 'AIRA is temporarily unavailable. Please try again shortly.'},
                status=503,
            )
        if not allowed:
            return JsonResponse(
                {
                    'error': (
                        'You are sending messages too quickly. Please wait a '
                        'moment and try again.'
                    ),
                },
                status=429,
            )
        try:
            reply = ask(request.user, question)
        except Exception:
            # Never leak a database/provider exception through the chat API.
            logger.exception('AIRA could not answer a request for user %s', request.user.pk)
            self._audit_error(request)
            return JsonResponse(
                {'error': 'AIRA is temporarily unavailable. Please try again shortly.'},
                status=503,
            )
        self._audit_question(request, question, reply)
        return JsonResponse(reply)

    @staticmethod
    def _audit_question(request, question, reply):
        """Record the request intent without storing confidential content."""
        try:
            AuditLog.objects.create(
                actor=request.user,
                action='AIRA_QUERY',
                object_type='AiraQuery',
                details={
                    'intent': reply.get('intent', ''),
                    'refused': reply.get('intent') == 'refused',
                    'question_length': len(question),
                },
            )
        except Exception:
            # Auditing must never break the user-facing reply, but operators
            # still need a diagnostic when the audit store is unavailable.
            logger.exception('Could not write AIRA audit event for user %s', request.user.pk)

    @staticmethod
    def _audit_error(request):
        """Audit an AIRA service failure without retaining the user's message."""
        try:
            AuditLog.objects.create(
                actor=request.user,
                action='AIRA_ERROR',
                object_type='AiraQuery',
                details={'stage': 'service_or_rate_limit'},
            )
        except Exception:
            logger.exception('Could not write AIRA error audit event for user %s', request.user.pk)
