from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accreditation.models import (
    AccreditationArea,
    AccreditationCycle,
    AccreditationLevel,
    AccreditationSubArea,
    EvidenceFile,
    EvidenceRequirement,
    EvidenceSubmission,
    EvidenceVersion,
)
from core.access import accessible_repository_submissions
from core.models import Department, Notification, Role, RoleAssignment, UserProfile
from resources.models import CommunicationMessage, Conversation, ConversationParticipant


class DocumentRepositoryAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.program_head_role = Role.objects.create(code='PROGRAM_HEAD', name='Program Head')
        cls.admin_role = Role.objects.create(code='ADMIN', name='Admin')
        cls.qa_role = Role.objects.create(code='QA', name='QA')
        cls.dean_role = Role.objects.create(code='DEAN', name='Dean')
        cls.engineering = Department.objects.create(
            code='ENG',
            name='College of Engineering',
            kind=Department.DEPARTMENT,
        )
        cls.civil = Department.objects.create(
            code='ENG-BSCIV',
            name='Bachelor of Science in Civil Engineering',
            kind=Department.PROGRAM,
            parent=cls.engineering,
        )
        cls.business = Department.objects.create(
            code='BUS',
            name='College of Business',
            kind=Department.DEPARTMENT,
        )
        cycle = AccreditationCycle.objects.create(
            name='Test Cycle',
            academic_year='2025-2026',
            status=AccreditationCycle.ACTIVE,
            is_active=True,
        )
        level = AccreditationLevel.objects.create(cycle=cycle, code='I', name='Level I')
        area = AccreditationArea.objects.create(
            level=level,
            code='Area I',
            name='Philosophy and Objectives',
            slug='area-i',
        )
        subarea = AccreditationSubArea.objects.create(area=area, code='1.1', title='Mission')
        cls.requirement = EvidenceRequirement.objects.create(
            area=area,
            subarea=subarea,
            code='1.1.1',
            title='Mission evidence',
            required_description='Provide the approved mission document.',
        )

        cls.uploader = cls.make_user(
            'uploader',
            cls.program_head_role,
            cls.civil,
        )
        cls.admin = cls.make_user('admin', cls.admin_role, cls.business)
        cls.qa = cls.make_user('qa', cls.qa_role, cls.business)
        cls.dean = cls.make_user('dean', cls.dean_role, cls.business)

        cls.communication_conversation = Conversation.objects.create()
        ConversationParticipant.objects.bulk_create(
            [
                ConversationParticipant(
                    conversation=cls.communication_conversation,
                    user=cls.uploader,
                ),
                ConversationParticipant(
                    conversation=cls.communication_conversation,
                    user=cls.qa,
                ),
            ],
        )
        CommunicationMessage.objects.create(
            conversation=cls.communication_conversation,
            sender=cls.qa,
            body=(
                'Good morning. I reviewed the Area II submission and found '
                'that the faculty credentials need to be updated for AY 2025-2026.'
            ),
        )
        CommunicationMessage.objects.create(
            conversation=cls.communication_conversation,
            sender=cls.uploader,
            body=(
                'Understood. I will compile everything and submit by July 20 '
                'to give enough buffer for review.'
            ),
        )

        cls.civil_submission = cls.make_submission(cls.civil, cls.uploader)
        cls.business_submission = cls.make_submission(cls.business, cls.uploader)
        for submission in (cls.civil_submission, cls.business_submission):
            version = EvidenceVersion.objects.create(
                submission=submission,
                version_number=1,
                submitted_by=cls.uploader,
            )
            EvidenceFile.objects.create(
                version=version,
                uploaded_by=cls.uploader,
                original_name=f'{submission.department.code} evidence.pdf',
            )

    @classmethod
    def make_user(cls, username, role, department):
        user = get_user_model().objects.create_user(username=username, password='password')
        profile = UserProfile.objects.create(
            user=user,
            department=department,
            approval_status=UserProfile.APPROVED,
        )
        assignment = RoleAssignment.objects.create(
            user=user,
            role=role,
            department=department,
            is_approved=True,
        )
        profile.active_assignment = assignment
        profile.save(update_fields=['active_assignment'])
        return user

    @classmethod
    def make_submission(cls, department, program_head):
        return EvidenceSubmission.objects.create(
            requirement=cls.requirement,
            department=department,
            program_head=program_head,
            created_by=program_head,
        )

    def test_program_head_sees_only_active_program_documents(self):
        submissions = accessible_repository_submissions(self.uploader)

        self.assertEqual(set(submissions), {self.civil_submission})

    def test_admin_and_qa_can_see_all_repository_documents(self):
        self.assertEqual(
            set(accessible_repository_submissions(self.admin)),
            {self.civil_submission, self.business_submission},
        )
        self.assertEqual(
            set(accessible_repository_submissions(self.qa)),
            {self.civil_submission, self.business_submission},
        )

    def test_admin_repository_shows_all_departments(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('resources:document_repository'))

        self.assertContains(response, '1.1 - Mission')
        self.assertContains(response, '1.1.1 - Mission evidence')
        self.assertContains(
            response,
            reverse('accreditation:evidence_detail', args=[self.civil_submission.id]),
        )
        self.assertContains(response, 'class="repo-view-btn">View</a>')
        self.assertContains(response, 'data-repo-filter="level"')
        self.assertContains(response, 'data-repo-filter="department"')
        self.assertContains(response, 'option value="Bachelor of Science in Civil Engineering"')
        self.assertContains(response, 'option value="College of Business"')
        self.assertContains(response, 'Departments')
        self.assertContains(response, 'All Documents')
        self.assertContains(response, 'College of Engineering')
        self.assertContains(response, 'College of Business')
        self.assertNotContains(response, 'Open Evidence Workspace')
        self.assertNotContains(response, 'repo-breadcrumb')
        self.assertNotContains(response, 'class="topbar-title">Document Repository</div>')

    def test_finished_repository_status_is_displayed_as_complied(self):
        self.business_submission.status = EvidenceSubmission.CLOSED
        self.business_submission.save(update_fields=['status'])
        self.client.force_login(self.admin)

        response = self.client.get(reverse('resources:document_repository'))

        self.assertContains(response, 'Complied')
        self.assertNotContains(response, '>Closed<')

    def test_topbar_search_control_is_available_on_authenticated_pages(self):
        self.client.force_login(self.uploader)

        response = self.client.get(reverse('resources:document_repository'))

        self.assertContains(response, 'data-global-search')
        self.assertContains(response, 'placeholder="Search..."')
        self.assertContains(response, 'aria-label="Search"')

    def test_program_head_repository_hides_department_panel(self):
        self.client.force_login(self.uploader)

        response = self.client.get(reverse('resources:document_repository'))

        self.assertNotContains(response, '<div class="department-title">Departments</div>')
        self.assertContains(response, 'Accreditor')
        self.assertContains(response, 'PACUCOA')
        self.assertContains(response, 'aria-label="Filter by department"')

    def test_communication_title_is_not_repeated_in_topbar(self):
        self.client.force_login(self.uploader)

        response = self.client.get(reverse('resources:communication'))

        self.assertContains(response, '<h1>Communication</h1>')
        self.assertNotContains(response, 'class="topbar-title">Communication</div>')

    def test_communication_messages_render_as_chat_content(self):
        self.client.force_login(self.uploader)

        response = self.client.get(
            reverse('resources:communication'),
            {'user_id': self.qa.pk},
        )

        self.assertContains(
            response,
            'Good morning. I reviewed the Area II submission',
        )
        self.assertContains(
            response,
            'Understood. I will compile everything and submit by July 20',
        )
        self.assertNotContains(response, "{'author': 'Demo QA'")

    def test_communication_lists_only_qa_dean_and_program_head(self):
        self.client.force_login(self.uploader)

        response = self.client.get(reverse('resources:communication'))

        contacts = response.context['conversations']
        contact_names = {contact['name'] for contact in contacts}
        contact_ids = {contact['user_id'] for contact in contacts}

        self.assertEqual(contact_names, {'qa', 'dean'})
        self.assertNotIn(self.uploader.pk, contact_ids)
        self.assertNotIn(self.admin.pk, contact_ids)
        for excluded_contact in ('Dr. A. Villanueva', 'Prof. J. Reyes', 'Area III Review Team', 'Dr. E. Cruz'):
            self.assertNotContains(response, excluded_contact)

    def test_communication_message_submission_persists_after_refresh(self):
        self.client.force_login(self.uploader)

        response = self.client.post(
            reverse('resources:communication'),
            {
                'action': 'send',
                'recipient_id': self.dean.pk,
                'body': 'Please confirm when the department evidence is ready.',
            },
        )

        self.assertRedirects(
            response,
            f'{reverse("resources:communication")}?user_id={self.dean.pk}',
        )
        self.assertTrue(
            CommunicationMessage.objects.filter(
                sender=self.uploader,
                body='Please confirm when the department evidence is ready.',
            )
            .filter(conversation__participant_links__user=self.uploader)
            .filter(conversation__participant_links__user=self.dean)
            .exists(),
        )

        refreshed = self.client.get(
            reverse('resources:communication'),
            {'user_id': self.dean.pk},
        )

        self.assertContains(
            refreshed,
            'Please confirm when the department evidence is ready.',
        )

        notification = Notification.objects.get(
            user=self.dean,
            kind='message',
        )
        self.assertEqual(
            notification.target_url,
            f'{reverse("resources:communication")}?user_id={self.uploader.pk}',
        )

        self.client.force_login(self.dean)
        notifications = self.client.get(reverse('core:notifications'))
        self.assertContains(notifications, 'New message from')
        self.assertContains(notifications, 'Open chat')

        self.client.get(
            reverse('resources:communication'),
            {'user_id': self.uploader.pk},
        )
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)

    def test_authenticated_modules_share_aira_guidance(self):
        self.client.force_login(self.uploader)

        for url in (
            reverse('accreditation:levels_areas'),
            reverse('resources:document_repository'),
            reverse('resources:communication'),
            reverse('intelligence:reports_monitoring'),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, 'aria-label="AIRA Smart Companion"')
                self.assertContains(response, 'class="aira-companion-bubble"')
                self.assertContains(response, 'Smart Companion')

    def test_communication_rejects_recipients_outside_allowed_roles(self):
        self.client.force_login(self.uploader)

        response = self.client.post(
            reverse('resources:communication'),
            {
                'action': 'send',
                'recipient_id': self.admin.pk,
                'body': 'This should not be sent.',
            },
        )

        self.assertEqual(response.status_code, 403)
