from django.conf import settings
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
from .models import (
    AuditLog,
    CookiePreference,
    Notification,
    Policy,
    PolicyConsent,
)


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


POLICY_SUMMARIES = {
    Policy.COOKIE: (
        'Guidelines for cookies used to support secure authentication, session '
        'management, and essential AMS functionality.'
    ),
    Policy.PRIVACY: (
        'Information on how personal and institutional data is collected, '
        'processed, protected, retained, and used within the JMCFI '
        'Accreditation Management System.'
    ),
    Policy.TERMS: (
        'Guidelines and responsibilities governing authorized access and '
        'appropriate use of the JMCFI Accreditation Management System.'
    ),
    Policy.AIRA: (
        'Information on how the AIRA Smart Companion uses only the '
        'accreditation records you are authorized to access, and assists '
        'within the AMS.'
    ),
}


def _user_display_name(user):
    """Institutional greeting name: full name, first name, or a neutral fallback."""
    if not user or not user.is_authenticated:
        return 'User'
    return user.get_full_name() or user.first_name or user.username or 'User'


class ConsentView(LoginRequiredMixin, TemplateView):
    """Versioned institutional-consent screen gating AMS access.

    Rendered as a modal overlay on top of the login page (via
    ``core/consent_overlay.html`` extending ``accounts/login.html``), not as a
    separate layout page.
    """

    template_name = 'core/consent_overlay.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        policies = Policy.active_required()
        acknowledged = consent_service.acknowledged_versions(self.request.user)
        # Explicit per-policy prior acknowledgment (version + timestamp).
        prior = {
            pc.policy_id: pc
            for pc in self.request.user.policy_consents.filter(
                status=PolicyConsent.ACCEPTED,
            ).select_related('policy')
        }
        rows = []
        for policy in policies:
            ack = prior.get(policy.id)
            rows.append({
                'policy': policy,
                'summary': POLICY_SUMMARIES.get(
                    policy.policy_type,
                    'Information about this policy and how it applies to your use of the AMS.',
                ),
                'acknowledged_version': ack.version if ack else '',
                'acknowledged_at': ack.accepted_at if ack else None,
            })
        active_policies = {p.policy_type: p for p in Policy.active()}
        context.update({
            'page_title': 'Institutional Policies',
            'policies': rows,
            'consent_display_name': _user_display_name(self.request.user),
            'consent_open': True,
            'any_updates': any(
                row['acknowledged_version'] and row['acknowledged_version'] != row['policy'].version
                for row in rows
            ),
            'privacy_policy': active_policies.get(Policy.PRIVACY),
            'terms_policy': active_policies.get(Policy.TERMS),
            'cookie_policy': active_policies.get(Policy.COOKIE),
            'aira_notice': active_policies.get(Policy.AIRA),
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
        template_map = {
            Policy.PRIVACY: ['core/privacy_notice.html'],
            Policy.TERMS: ['core/policies/terms_of_use.html'],
            Policy.COOKIE: ['core/policies/cookie_policy.html'],
            Policy.AIRA: ['core/policies/aira_notice.html'],
        }
        return template_map.get(
            self.policy.policy_type,
            ['core/privacy_notice.html'],
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['policy'] = self.policy
        context['page_title'] = self.policy.title
        context['hide_topbar_title'] = True
        context['created_via_consent'] = True
        return context


class CookiePreferenceUpdateView(LoginRequiredMixin, View):
    """Persist a user's cookie preferences server-side (POST only, CSRF-protected).

    The deployment currently uses no optional cookie categories, so the only
    permitted state is "essential cookies always active". When optional
    categories are added to ``settings.COOKIE_OPTIONAL_CATEGORIES`` the same
    endpoint persists per-category on/off choices; unknown categories are
    never accepted.
    """

    def post(self, request, *args, **kwargs):
        allowed = set(getattr(settings, 'COOKIE_OPTIONAL_CATEGORIES', []))
        submitted = request.POST.getlist('optional_cookies')
        optional = {category: category in submitted for category in allowed}

        preference, _ = CookiePreference.objects.update_or_create(
            user=request.user,
            defaults={'optional_cookies': optional},
        )
        AuditLog.objects.create(
            actor=request.user,
            action='COOKIE_PREFERENCES_SAVED',
            object_type='CookiePreference',
            object_id=str(preference.pk),
            details={'optional_categories': optional},
        )
        messages.success(request, 'Cookie preferences saved.')
        default_next = reverse('accounts:settings_profile')
        candidate = request.POST.get('next') or default_next
        return redirect(_safe_consent_next(request, candidate))


class ConsentWithdrawView(LoginRequiredMixin, View):
    """Revoke the authenticated user's own acknowledgment for a policy.

    Only non-required (informational) policies can be withdrawn through this
    endpoint. Required policies cannot be casually reversed because continued
    access depends on them; users must re-acknowledge the current version
    instead.
    """

    def post(self, request, *args, **kwargs):
        policy = Policy.objects.filter(
            pk=request.POST.get('policy_id'),
            is_required=False,
        ).first()
        if not policy:
            raise Http404('Policy not found or cannot be withdrawn.')
        withdrawn = consent_service.withdraw(request.user, policy)
        if withdrawn:
            messages.success(request, f'Acknowledgment of "{policy.title}" was withdrawn.')
        else:
            messages.error(request, 'No active acknowledgment to withdraw.')
        return redirect(reverse('accounts:settings_profile'))
