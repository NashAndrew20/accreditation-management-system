from django.urls import reverse
from django.views.generic import TemplateView

from accreditation.constants import COMPLETED_STATUSES, PENDING_STATUSES
from accreditation.db_views import status_label, status_tone
from accreditation.models import EvidenceFile
from core.access import accessible_repository_submissions, is_admin_user
from core.mixins import ApprovedUserRequiredMixin
from core.models import Department


class DocumentRepositoryView(ApprovedUserRequiredMixin, TemplateView):
    template_name = 'resources/document_repository.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        submissions = accessible_repository_submissions(self.request.user)
        repository_admin = is_admin_user(self.request.user)
        evidence_files = EvidenceFile.objects.filter(
            version__submission__in=submissions,
        ).select_related(
            'version__submission__requirement__area__level',
            'version__submission__requirement__subarea',
            'version__submission__department',
            'version__submission__program_head',
        )
        documents = []
        for evidence_file in evidence_files:
            submission = evidence_file.version.submission
            requirement = submission.requirement
            name = evidence_file.original_name or evidence_file.file.name or evidence_file.link_url
            if requirement.subarea:
                label = f'{requirement.subarea.code} - {requirement.subarea.title}'
            else:
                label = f'{requirement.code} - {requirement.title}'
            documents.append({
                'name': name,
                'label': label,
                'requirement_label': f'{requirement.code} - {requirement.title}',
                'detail_url': reverse('accreditation:evidence_detail', args=[submission.id]),
                'department': submission.department.name,
                'details': f'{requirement.area.code} · {requirement.area.level.name} · {submission.program_head.get_full_name() or submission.program_head.username}',
                'tags': [requirement.area.name, requirement.subarea.code if requirement.subarea else 'Evidence'],
                'version': f'v{evidence_file.version.version_number}',
                'updated': f'Updated {evidence_file.created_at:%b %d, %Y}',
                'status': status_label(submission.status),
                'tone': status_tone(submission.status),
                'icon_tone': 'rose',
            })
        departments = []
        if repository_admin:
            departments = [{'label': 'All Documents', 'active': True}]
            departments.extend(
                {'label': name, 'active': False}
                for name in Department.objects.filter(is_active=True)
                .order_by('name')
                .values_list('name', flat=True)
            )
        total = len(documents)
        completed = submissions.filter(status__in=COMPLETED_STATUSES).count()
        pending = submissions.filter(status__in=PENDING_STATUSES).count()
        context.update(
            {
                'page_title': 'Document Repository',
                'hide_topbar_title': True,
                'documents': documents,
                'departments': departments,
                'is_repository_admin': repository_admin,
                'repo_stats': [
                    {'label': 'Total Documents', 'value': total, 'tone': 'rose'},
                    {'label': 'Approved / Closed', 'value': completed, 'tone': 'green'},
                    {'label': 'Pending / Revision', 'value': pending, 'tone': 'gold'},
                ],
            }
        )
        return context


class CommunicationView(ApprovedUserRequiredMixin, TemplateView):
    template_name = 'resources/communication.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        conversations = [
            {
                'initials': 'AV',
                'name': 'Dr. A. Villanueva',
                'context': 'QA Office',
                'preview': 'Please resubmit Area II with updated credentials...',
                'time': '10:22 AM',
                'unread': 2,
                'active': True,
                'online': True,
                'pinned': True,
            },
            {
                'initials': 'JR',
                'name': 'Prof. J. Reyes',
                'context': 'College of Engineering',
                'preview': 'I have uploaded the revised syllabi for review.',
                'time': '9:45 AM',
                'unread': 0,
                'active': False,
                'online': True,
                'pinned': False,
            },
            {
                'initials': 'A3',
                'name': 'Area III Review Team',
                'context': 'Group · 5 members',
                'preview': 'Dr. Cruz: The assessment framework looks complete.',
                'time': 'Yesterday',
                'unread': 5,
                'active': False,
                'online': False,
                'pinned': False,
            },
            {
                'initials': 'EC',
                'name': 'Dr. E. Cruz',
                'context': 'College of Business (Dean)',
                'preview': "Approved the Dean's review for Area V.",
                'time': 'Yesterday',
                'unread': 0,
                'active': False,
                'online': False,
                'pinned': False,
            },
        ]
        messages = [
            {
                'author': 'Dr. A. Villanueva',
                'initials': 'AV',
                'text': 'Good morning, Prof. Reyes. I reviewed your Area II submission and found that the faculty credentials need to be updated for AY 2025-2026.',
                'time': '9:30 AM',
                'mine': False,
            },
            {
                'author': 'You',
                'initials': 'MS',
                'text': 'Good morning, Dr. Villanueva. Thank you for the feedback. I will gather the updated credentials from all faculty members.',
                'time': '9:35 AM',
                'mine': True,
            },
            {
                'author': 'Dr. A. Villanueva',
                'initials': 'AV',
                'text': 'Please prioritize the full-time faculty. Also ensure that Special Professional Licenses are included. The deadline is July 25.',
                'time': '9:42 AM',
                'mine': False,
            },
            {
                'author': 'You',
                'initials': 'MS',
                'text': 'Understood. I will compile everything and submit by July 20 to give enough buffer for review.',
                'time': '9:48 AM',
                'mine': True,
            },
        ]
        context.update(
            {
                'page_title': 'Communication',
                'conversations': conversations,
                'chat_messages': messages,
                'active_conversation': conversations[0],
            }
        )
        return context
