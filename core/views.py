from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.timesince import timesince
from django.views.generic import TemplateView

from .access import accessible_submissions, can_approve_accounts, is_admin_user
from .mixins import ApprovedUserRequiredMixin
from .models import AuditLog, Notification


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
