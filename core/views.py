from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.timesince import timesince
from django.utils.timezone import now
from django.views.generic import TemplateView, View
from django.views.decorators.http import require_POST

from . import consent as consent_service
from .access import accessible_submissions, can_approve_accounts, is_admin_user
from .mixins import ApprovedUserRequiredMixin
from .models import AuditLog, Notification, Policy


NOTIFICATION_PRESENTATION = {
    'revision': ('Revision Requested', 'alert', 'rose'),
    'submission': ('Evidence Submitted', 'file', 'blue'),
    'review': ('Review Update', 'check', 'green'),
    'account': ('Account Update', 'users', 'green'),
    'deadline': ('Deadline Reminder', 'clock', 'gold'),
    'message': ('New Message', 'message', 'blue'),
    'system': ('System Notice', 'bolt', 'maroon'),
}


class NotificationsView(ApprovedUserRequiredMixin, TemplateView):
    template_name = 'core/notifications.html'

    def post(self, request, *args, **kwargs):
        if request.POST.get('action') == 'mark_all_read':
            Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
            messages.success(request, 'All notifications marked as read.')
        else:
            Notification.objects.filter(user=request.user, pk=request.POST.get('notification_id')).update(is_read=True)
        return redirect('core:notifications')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rows = []
        notifications = Notification.objects.filter(user=self.request.user).select_related('submission')
        for notification in notifications:
            fallback_title, icon, tone = NOTIFICATION_PRESENTATION.get(
                notification.kind,
                (notification.title, 'bell', 'slate'),
            )
            rows.append({
                'id': notification.id,
                'title': notification.title or fallback_title,
                'message': notification.message,
                'time_label': f'{timesince(notification.created_at)} ago',
                'icon': icon,
                'tone': tone,
                'unread': not notification.is_read,
                'target_url': notification.target_url or (
                    reverse('accreditation:evidence_detail', args=[notification.submission_id])
                    if notification.submission_id else ''
                ),
                'target_label': 'Open chat' if notification.kind == 'message' else 'Open evidence',
            })
        unread_total = sum(1 for item in rows if item['unread'])
        context.update({
            'page_title': 'Notifications',
            'notifications': rows,
            'unread_total': unread_total,
            'total_notifications': len(rows),
        })
        return context


class AuditHistoryView(ApprovedUserRequiredMixin, TemplateView):
    template_name = 'core/audit_history.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if is_admin_user(self.request.user) or can_approve_accounts(self.request.user):
            events = AuditLog.objects.all()
        else:
            events = AuditLog.objects.filter(submission__in=accessible_submissions(self.request.user))
        context.update({
            'page_title': 'Audit History',
            'events': events.select_related('actor', 'submission__requirement', 'submission__department')[:200],
        })
        return context


class PrivacyNoticeView(TemplateView):
    """Public data privacy notice and policy for the accreditation portal."""

    template_name = 'core/privacy_notice.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Data Privacy Notice & Policy'
        context['hide_topbar_title'] = True
        context['policy'] = Policy.objects.filter(
            policy_type=Policy.PRIVACY,
            status=Policy.ACTIVE,
            is_required=True,
        ).first()
        context['created_via_consent'] = False
        return context


def _safe_consent_next(request, candidate):
    """Same-host redirect target after consent, or the dashboard by default."""
    if candidate and candidate.startswith('/') and not candidate.startswith('//'):
        return candidate
    return reverse('dashboard:index')


class ConsentView(LoginRequiredMixin, TemplateView):
    """Full-page institutional consent screen gating AMS access."""

    template_name = 'core/consent.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        policies = Policy.active_required()
        acknowledged = consent_service.acknowledged_versions(self.request.user)
        # Explicit per-policy prior acknowledgment (version + timestamp).
        prior = {
            pc.policy_id: pc
            for pc in self.request.user.policy_consents.select_related('policy')
        }
        rows = []
        for policy in policies:
            ack = prior.get(policy.id)
            rows.append({
                'policy': policy,
                'acknowledged_version': ack.version if ack else '',
                'acknowledged_at': ack.accepted_at if ack else None,
            })
        context.update({
            'page_title': 'Privacy & Terms',
            'policies': rows,
            'any_updates': any(
                row['acknowledged_version'] and row['acknowledged_version'] != row['policy'].version
                for row in rows
            ),
            'next_url': _safe_consent_next(self.request, self.request.GET.get('next')),
        })
        return context


class ConsentAcceptView(LoginRequiredMixin, View):
    """Record explicit, versioned consent; must be a POST."""

    def post(self, request, *args, **kwargs):
        policies = list(Policy.active_required())
        if not policies:
            return redirect(_safe_consent_next(request, request.POST.get('next')))

        versions = {
            p.policy_type: request.POST.get(f'version_{p.policy_type}')
            for p in policies
        }
        acknowledged = request.POST.get('acknowledge') == '1'
        # Server-side authority: only the exactly-matching current version counts.
        valid = acknowledged and all(
            versions[p.policy_type] == p.version for p in policies
        )
        if not valid:
            messages.error(
                request,
                'Please confirm each policy version shown before continuing.',
            )
            return redirect('core:consent')

        for policy in policies:
            consent_service.acknowledge(request.user, policy, policy.version)
        return redirect(_safe_consent_next(request, request.POST.get('next')))


class PolicyDetailView(TemplateView):
    """Public route to a specific active policy version."""

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.policy = Policy.objects.filter(
            slug=self.kwargs.get('slug'),
            status=Policy.ACTIVE,
        ).first()
        if not self.policy:
            raise Http404('Policy not found')

    def get_template_names(self):
        if self.policy.policy_type == Policy.TERMS:
            return ['core/policies/terms_of_use.html']
        return ['core/privacy_notice.html']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['policy'] = self.policy
        context['page_title'] = self.policy.title
        context['hide_topbar_title'] = True
        context['created_via_consent'] = True
        return context
