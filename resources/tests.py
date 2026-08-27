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
from core.models import Department, Role, RoleAssignment, UserProfile


class DocumentRepositoryAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.program_head_role = Role.objects.create(code='PROGRAM_HEAD', name='Program Head')
        cls.admin_role = Role.objects.create(code='ADMIN', name='Admin')
        cls.qa_role = Role.objects.create(code='QA', name='QA')
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

        self.assertContains(response, 'Departments')
        self.assertContains(response, 'All Documents')
        self.assertContains(response, 'College of Engineering')
        self.assertContains(response, 'College of Business')
        self.assertNotContains(response, 'Open Evidence Workspace')
        self.assertNotContains(response, 'repo-breadcrumb')
        self.assertNotContains(response, 'class="topbar-title">Document Repository</div>')

    def test_program_head_repository_hides_department_panel(self):
        self.client.force_login(self.uploader)

        response = self.client.get(reverse('resources:document_repository'))

        self.assertNotContains(response, 'Departments')
        self.assertContains(response, 'Accreditor')
        self.assertContains(response, 'PACUCOA')

    def test_communication_title_is_not_repeated_in_topbar(self):
        self.client.force_login(self.uploader)

        response = self.client.get(reverse('resources:communication'))

        self.assertContains(response, '<h1>Communication</h1>')
        self.assertNotContains(response, 'class="topbar-title">Communication</div>')
