from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Prefetch
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import TemplateView

from accreditation.constants import COMPLETED_STATUSES, PENDING_STATUSES
from accreditation.db_views import status_label, status_tone
from accreditation.models import EvidenceFile
from core.access import accessible_repository_submissions, is_admin_user
from core.mixins import ApprovedUserRequiredMixin
from core.models import Department, RoleAssignment, UserProfile

from .forms import CommunicationMessageForm
from .models import CommunicationMessage, Conversation, ConversationParticipant


COMMUNICATION_ROLE_CODES = ('QA', 'DEAN', 'PROGRAM_HEAD')


def _user_name(user):
    return user.get_full_name() or user.username


def _user_initials(user):
    name_parts = [part for part in (user.first_name, user.last_name) if part]
    if len(name_parts) >= 2:
        return ''.join(part[0] for part in name_parts[:2]).upper()
    return (user.username[:2] or '?').upper()


def _message_time(created_at):
    local_time = timezone.localtime(created_at)
    today = timezone.localdate()
    if local_time.date() == today:
        return local_time.strftime('%I:%M %p').lstrip('0')
    if (today - local_time.date()).days == 1:
        return 'Yesterday'
    return local_time.strftime('%b %d')


def _communication_assignment_queryset():
    return RoleAssignment.objects.filter(
        is_approved=True,
        role__code__in=COMMUNICATION_ROLE_CODES,
        role__is_active=True,
        role__is_internal=True,
        department__is_active=True,
    ).select_related('role', 'department').order_by(
        'role__sort_order',
        'department__name',
    )


def _communication_contacts(user):
    User = get_user_model()
    return (
        User.objects.filter(
            is_active=True,
            profile__approval_status=UserProfile.APPROVED,
            role_assignments__is_approved=True,
            role_assignments__role__code__in=COMMUNICATION_ROLE_CODES,
            role_assignments__role__is_active=True,
            role_assignments__role__is_internal=True,
            role_assignments__department__is_active=True,
        )
        .exclude(pk=user.pk)
        .select_related('profile')
        .prefetch_related(
            Prefetch(
                'role_assignments',
                queryset=_communication_assignment_queryset(),
                to_attr='communication_assignments',
            ),
        )
        .distinct()
        .order_by('first_name', 'last_name', 'username')
    )


def _contact_assignment(user):
    assignments = getattr(user, 'communication_assignments', [])
    active_assignment_id = getattr(
        getattr(user, 'profile', None),
        'active_assignment_id',
        None,
    )
    return next(
        (
            assignment
            for assignment in assignments
            if assignment.pk == active_assignment_id
        ),
        assignments[0] if assignments else None,
    )


def _direct_conversation(user, other_user):
    return (
        Conversation.objects.annotate(
            participant_count=Count('participant_links', distinct=True),
        )
        .filter(
            participant_links__user=user,
        )
        .filter(
            participant_links__user=other_user,
        )
        .filter(participant_count=2)
        .first()
    )


def _get_or_create_direct_conversation(user, other_user):
    conversation = _direct_conversation(user, other_user)
    if conversation:
        return conversation

    with transaction.atomic():
        conversation = _direct_conversation(user, other_user)
        if conversation:
            return conversation
        conversation = Conversation.objects.create()
        ConversationParticipant.objects.bulk_create(
            [
                ConversationParticipant(conversation=conversation, user=user),
                ConversationParticipant(conversation=conversation, user=other_user),
            ],
        )
    return conversation


def _conversation_contact(user, contact, selected_id):
    assignment = _contact_assignment(contact)
    conversation = _direct_conversation(user, contact)
    latest_message = None
    unread_count = 0
    if conversation:
        latest_message = (
            conversation.messages.order_by('-created_at').first()
        )
        unread_count = conversation.messages.filter(
            is_read=False,
        ).exclude(sender_id=user.pk).count()

    return {
        'user_id': contact.pk,
        'initials': _user_initials(contact),
        'name': _user_name(contact),
        'context': (
            f'{assignment.department.name} · {assignment.role.name}'
            if assignment
            else 'Internal accreditation team'
        ),
        'preview': (
            latest_message.body
            if latest_message
            else 'No messages yet. Start a conversation.'
        ),
        'time': _message_time(latest_message.created_at) if latest_message else '',
        'unread': unread_count,
        'active': contact.pk == selected_id,
        'online': contact.is_active,
    }


def _conversation_messages(conversation, current_user):
    if not conversation:
        return []
    return [
        {
            'author': 'You' if message.sender_id == current_user.pk else _user_name(message.sender),
            'initials': _user_initials(message.sender),
            'text': message.body,
            'time': _message_time(message.created_at),
            'mine': message.sender_id == current_user.pk,
        }
        for message in conversation.messages.select_related('sender').all()
    ]


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
                    {'label': 'Complied', 'value': completed, 'tone': 'green'},
                    {'label': 'Pending / Revision', 'value': pending, 'tone': 'gold'},
                ],
            }
        )
        return context


class CommunicationView(ApprovedUserRequiredMixin, TemplateView):
    template_name = 'resources/communication.html'

    @staticmethod
    def _parse_user_id(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _build_context(self, form=None, selected_contact_id=None):
        context = super().get_context_data()
        contacts = list(_communication_contacts(self.request.user))

        selected_contact = next(
            (
                contact
                for contact in contacts
                if contact.pk == selected_contact_id
            ),
            contacts[0] if contacts else None,
        )
        selected_id = selected_contact.pk if selected_contact else None
        conversation = (
            _direct_conversation(self.request.user, selected_contact)
            if selected_contact
            else None
        )

        if conversation:
            conversation.messages.filter(
                is_read=False,
            ).exclude(sender_id=self.request.user.pk).update(is_read=True)

        conversations = [
            _conversation_contact(self.request.user, contact, selected_id)
            for contact in contacts
        ]
        context.update(
            {
                'page_title': 'Communication',
                'conversations': conversations,
                'chat_messages': _conversation_messages(
                    conversation,
                    self.request.user,
                ),
                'active_conversation': (
                    next(
                        item
                        for item in conversations
                        if item['user_id'] == selected_id
                    )
                    if selected_id
                    else None
                ),
                'message_form': form if form is not None else CommunicationMessageForm(),
            }
        )
        return context

    def get_context_data(self, **kwargs):
        selected_contact_id = self._parse_user_id(
            self.request.GET.get('user_id'),
        )
        return self._build_context(selected_contact_id=selected_contact_id)

    def post(self, request, *args, **kwargs):
        recipient_id = self._parse_user_id(request.POST.get('recipient_id'))
        recipient = next(
            (
                contact
                for contact in _communication_contacts(request.user)
                if contact.pk == recipient_id
            ),
            None,
        )
        if recipient is None:
            raise PermissionDenied('You cannot message this account.')

        form = CommunicationMessageForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                conversation = _get_or_create_direct_conversation(
                    request.user,
                    recipient,
                )
                CommunicationMessage.objects.create(
                    conversation=conversation,
                    sender=request.user,
                    body=form.cleaned_data['body'],
                )
                conversation.save(update_fields=('updated_at',))
            return redirect(
                f'{reverse("resources:communication")}?user_id={recipient.pk}',
            )

        return self.render_to_response(
            self._build_context(
                form=form,
                selected_contact_id=recipient.pk,
            ),
        )
