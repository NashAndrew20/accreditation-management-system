from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from django.utils import timezone

from core.models import AuditLog, Department, Notification, Role, RoleAssignment, UserProfile

from .models import (
    AccreditationArea,
    AccreditationCycle,
    AccreditationLevel,
    AccreditationSubArea,
    AreaAssignment,
    EvidenceFile,
    EvidenceRequirement,
    EvidenceReview,
    EvidenceSubmission,
    EvidenceVersion,
)
from .cache import ACTIVE_STRUCTURE_CACHE_KEY
from .workflow import approve_submission, request_revision, submit_submission


class AccreditationWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.roles = {
            code: Role.objects.create(code=code, name=name, sort_order=index)
            for index, (code, name) in enumerate((
                ('PROGRAM_HEAD', 'Program Head'),
                ('DEAN', 'Dean'),
                ('AREA_CHAIR', 'Area Chair'),
                ('QA', 'QA'),
            ))
        }
        cls.department = Department.objects.create(code='ENG', name='College of Engineering')
        cls.program = Department.objects.create(
            code='ENG-BSCIV',
            name='Bachelor of Science in Civil Engineering',
            kind=Department.PROGRAM,
            parent=cls.department,
        )
        cls.cycle = AccreditationCycle.objects.create(
            name='Test Cycle', academic_year='2025-2026', status=AccreditationCycle.ACTIVE, is_active=True,
        )
        cls.level = AccreditationLevel.objects.create(cycle=cls.cycle, code='I', name='Level I')
        cls.area = AccreditationArea.objects.create(level=cls.level, code='Area I', name='Philosophy and Objectives', slug='area-i')
        cls.subarea = AccreditationSubArea.objects.create(area=cls.area, code='1.1', title='Mission')
        cls.requirement = EvidenceRequirement.objects.create(
            area=cls.area,
            subarea=cls.subarea,
            code='1.1.1',
            title='Mission evidence',
            required_description='Provide the approved mission document.',
            deadline=timezone.localdate(),
        )
        cls.revision_requirement = EvidenceRequirement.objects.create(
            area=cls.area,
            subarea=cls.subarea,
            code='1.1.2',
            title='Vision evidence',
            required_description='Provide the approved vision document.',
        )
        cls.program_head = cls.make_user('program-head', 'Program Head', cls.roles['PROGRAM_HEAD'], cls.program)
        cls.dean = cls.make_user('dean', 'Dean', cls.roles['DEAN'], cls.department)
        cls.area_chair = cls.make_user('area-chair', 'Area Chair', cls.roles['AREA_CHAIR'], cls.department)
        cls.qa = cls.make_user('qa', 'QA', cls.roles['QA'], cls.department)
        cls.area_chair.role_assignment.assigned_areas.add(cls.area)

    def setUp(self):
        cache.clear()

    @classmethod
    def make_user(cls, username, name, role, department):
        user = get_user_model().objects.create_user(username=username, password='secure-password')
        user.first_name = name
        user.save(update_fields=['first_name'])
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
        profile.save(update_fields=['active_assignment', 'updated_at'])
        user.role_assignment = assignment
        return user

    def make_submission(self, requirement=None):
        return EvidenceSubmission.objects.create(
            requirement=requirement or self.requirement,
            department=self.program,
            program_head=self.program_head,
            created_by=self.program_head,
        )

    def move_submission_to_qa_review(self, submission):
        submit_submission(
            submission,
            self.program_head,
            'meets the requirement',
            'implemented in the program',
            link_url='https://example.com/evidence',
        )
        approve_submission(submission, self.dean, 'Dean review complete.')
        approve_submission(submission, self.area_chair, 'Area Chair review complete.')
        submission.refresh_from_db()
        return submission

    def test_submission_moves_through_all_internal_review_stages_and_closes(self):
        submission = self.make_submission()
        submit_submission(submission, self.program_head, 'meets', 'implemented', link_url='https://example.com/mission')
        submission.refresh_from_db()
        self.assertEqual(submission.status, EvidenceSubmission.UNDER_DEAN_REVIEW)
        self.assertEqual(submission.current_reviewer_id, self.dean.id)
        self.assertEqual(EvidenceVersion.objects.filter(submission=submission).count(), 1)

        approve_submission(submission, self.dean, 'Dean review complete.')
        submission.refresh_from_db()
        self.assertEqual(submission.status, EvidenceSubmission.UNDER_AREA_CHAIR_REVIEW)
        self.assertEqual(submission.current_reviewer_id, self.area_chair.id)

        approve_submission(submission, self.area_chair, 'Area review complete.')
        submission.refresh_from_db()
        self.assertEqual(submission.status, EvidenceSubmission.UNDER_QA_REVIEW)
        self.assertEqual(submission.current_reviewer_id, self.qa.id)

        approve_submission(submission, self.qa, 'Final internal review complete.')
        submission.refresh_from_db()
        self.assertEqual(submission.status, EvidenceSubmission.CLOSED)
        self.assertIsNotNone(submission.closed_at)
        self.assertEqual(EvidenceReview.objects.filter(submission=submission).count(), 4)
        self.assertTrue(EvidenceReview.objects.filter(submission=submission, decision=EvidenceReview.COMPLIED_DECISION).exists())
        self.assertTrue(EvidenceReview.objects.filter(submission=submission, decision=EvidenceReview.CLOSED_DECISION).exists())

    @override_settings(DEMO_MODE=True)
    def test_three_account_demo_can_forward_dean_review_to_qa(self):
        self.area_chair.role_assignment.is_approved = False
        self.area_chair.role_assignment.save(update_fields=['is_approved'])
        submission = self.make_submission()
        submit_submission(submission, self.program_head, 'meets', 'implemented', link_url='https://example.com/mission')

        approve_submission(submission, self.dean, 'Dean demo approval.')

        submission.refresh_from_db()
        self.assertEqual(submission.status, EvidenceSubmission.UNDER_QA_REVIEW)
        self.assertEqual(submission.current_reviewer_id, self.qa.id)

    def test_revision_returns_to_same_reviewer_and_preserves_versions_and_remarks(self):
        submission = self.make_submission(self.revision_requirement)
        submit_submission(submission, self.program_head, 'first version', 'needs work', link_url='https://example.com/vision')
        request_revision(submission, self.dean, 'Please add the signed approval page.')
        submission.refresh_from_db()
        self.assertEqual(submission.status, EvidenceSubmission.NEEDS_REVISION)
        self.assertEqual(submission.current_reviewer_id, self.program_head.id)
        self.assertEqual(submission.revision_return_reviewer_id, self.dean.id)

        submit_submission(submission, self.program_head, 'revised version', 'updated and signed')
        submission.refresh_from_db()
        self.assertEqual(submission.status, EvidenceSubmission.UNDER_DEAN_REVIEW)
        self.assertEqual(submission.current_reviewer_id, self.dean.id)
        self.assertEqual(EvidenceVersion.objects.filter(submission=submission).count(), 2)
        self.assertEqual(EvidenceReview.objects.filter(submission=submission).count(), 1)
        self.assertEqual(EvidenceReview.objects.get(submission=submission).remarks, 'Please add the signed approval page.')

    def test_reviewer_must_be_current_assignee(self):
        submission = self.make_submission()
        submit_submission(submission, self.program_head, 'meets', 'implemented', link_url='https://example.com/mission')
        with self.assertRaises(PermissionDenied):
            approve_submission(submission, self.area_chair, 'Wrong stage.')

    def test_program_head_cannot_manage_another_program_submission(self):
        other_program = Department.objects.create(
            code='BUS-BSBA', name='Bachelor of Science in Business Administration', kind=Department.PROGRAM,
        )
        other_user = self.make_user('other-head', 'Other', self.roles['PROGRAM_HEAD'], other_program)
        submission = self.make_submission()
        with self.assertRaises(PermissionDenied):
            submit_submission(submission, other_user, 'not allowed', 'not allowed')

    def test_evidence_pages_are_connected_to_database_records(self):
        self.client.force_login(self.program_head)
        self.assertEqual(self.client.get(reverse('accreditation:levels_areas')).status_code, 200)
        self.assertEqual(self.client.get(reverse('accreditation:area_details', args=[self.area.slug])).status_code, 200)
        response = self.client.get(reverse('accreditation:submission_workspace_subarea', args=[self.area.slug, '1-1']))
        self.assertEqual(response.status_code, 200)
        submission = EvidenceSubmission.objects.get(requirement=self.requirement, department=self.program)
        self.assertEqual(self.client.get(reverse('accreditation:evidence_detail', args=[submission.id])).status_code, 200)

    def test_levels_and_areas_cache_public_accreditation_structure(self):
        self.client.force_login(self.program_head)

        response = self.client.get(reverse('accreditation:levels_areas'))

        self.assertEqual(response.status_code, 200)
        cached_structure = cache.get(ACTIVE_STRUCTURE_CACHE_KEY)
        self.assertEqual(cached_structure['cycle']['name'], 'Test Cycle')
        self.assertEqual(cached_structure['levels'][0]['areas'][0]['code'], 'Area I')

    def test_jwt_evidence_api_uses_existing_role_scope(self):
        submission = self.make_submission()
        api_client = APIClient()

        token_response = api_client.post(reverse('api_auth:token'), {
            'username': self.program_head.username,
            'password': 'secure-password',
        }, format='json')
        self.assertEqual(token_response.status_code, 200)

        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_response.data['access']}")
        response = api_client.get(reverse('api_evidence:list'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], submission.id)
        self.assertEqual(response.data[0]['evidence_code'], self.requirement.code)

    def test_qa_does_not_see_feedback_in_pacucoa_workspace_until_reviewing_submission(self):
        submission = self.make_submission()
        submission.status = EvidenceSubmission.UNDER_DEAN_REVIEW
        submission.current_reviewer = self.dean
        submission.current_review_role = self.roles['DEAN']
        submission.save(update_fields=['status', 'current_reviewer', 'current_review_role', 'last_updated'])
        EvidenceReview.objects.create(
            submission=submission,
            reviewer=self.dean,
            reviewer_role=self.roles['DEAN'],
            from_status=EvidenceSubmission.UNDER_DEAN_REVIEW,
            to_status=EvidenceSubmission.UNDER_AREA_CHAIR_REVIEW,
            decision=EvidenceReview.APPROVED,
            remarks='Department review feedback should stay out of QA browsing.',
        )

        self.client.force_login(self.qa)
        workspace_response = self.client.get(
            reverse('accreditation:submission_workspace_subarea', args=[self.area.slug, '1-1']),
        )
        self.assertNotContains(workspace_response, 'Reviewer Remarks')
        self.assertNotContains(workspace_response, 'Department review feedback should stay out of QA browsing.')

        evidence_response = self.client.get(reverse('accreditation:evidence_detail', args=[submission.id]))
        self.assertNotContains(evidence_response, 'Review history')
        self.assertNotContains(evidence_response, 'Department review feedback should stay out of QA browsing.')

        submission.status = EvidenceSubmission.UNDER_QA_REVIEW
        submission.current_reviewer = self.qa
        submission.current_review_role = self.roles['QA']
        submission.save(update_fields=['status', 'current_reviewer', 'current_review_role', 'last_updated'])
        review_response = self.client.get(reverse('accreditation:evidence_review', args=[submission.id]))
        self.assertContains(review_response, 'Review history')
        self.assertContains(review_response, 'Department review feedback should stay out of QA browsing.')
        evidence_response = self.client.get(reverse('accreditation:evidence_detail', args=[submission.id]))
        self.assertContains(evidence_response, 'Review submission')

    def test_qa_can_review_assigned_submission_from_area_workspace_and_request_revision(self):
        submission = self.move_submission_to_qa_review(self.make_submission())
        self.client.force_login(self.qa)

        workspace_response = self.client.get(
            reverse('accreditation:submission_workspace_subarea', args=[self.area.slug, '1-1']),
        )
        self.assertContains(workspace_response, 'Review submission')
        self.assertContains(
            workspace_response,
            reverse('accreditation:evidence_review', args=[submission.id]),
        )

        review_response = self.client.get(reverse('accreditation:evidence_review', args=[submission.id]))
        self.assertContains(review_response, 'Review decision')
        self.assertContains(review_response, 'Approve / Mark Complied')
        self.assertContains(review_response, 'Mark non-complied')
        self.assertContains(review_response, 'Feedback / remarks')
        self.assertContains(review_response, 'Area Chair review complete.')
        self.assertContains(review_response, 'https://example.com/evidence')

        response = self.client.post(
            reverse('accreditation:evidence_review', args=[submission.id]),
            {
                'action': 'revision',
                'remarks': 'Please add the signed approval page.',
            },
        )
        self.assertRedirects(response, reverse('accreditation:review_workflow'))
        submission.refresh_from_db()
        self.assertEqual(submission.status, EvidenceSubmission.NEEDS_REVISION)
        self.assertEqual(submission.current_reviewer_id, self.program_head.id)
        self.assertEqual(
            submission.reviews.latest('created_at').remarks,
            'Please add the signed approval page.',
        )

    def test_qa_can_approve_assigned_submission_from_review_page(self):
        submission = self.move_submission_to_qa_review(self.make_submission())
        self.client.force_login(self.qa)

        response = self.client.post(
            reverse('accreditation:evidence_review', args=[submission.id]),
            {
                'action': 'approve',
                'remarks': 'Final internal compliance verified.',
            },
        )
        self.assertRedirects(response, reverse('accreditation:review_workflow'))
        submission.refresh_from_db()
        self.assertEqual(submission.status, EvidenceSubmission.CLOSED)
        self.assertTrue(
            submission.reviews.filter(
                decision=EvidenceReview.COMPLIED_DECISION,
                remarks='Final internal compliance verified.',
            ).exists()
        )

    def test_qa_area_workspace_is_read_only(self):
        self.make_submission()
        self.client.force_login(self.qa)

        response = self.client.get(
            reverse('accreditation:submission_workspace_subarea', args=[self.area.slug, '1-1']),
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="action" value="submit"')
        self.assertNotContains(response, 'name="action" value="resubmit"')
        self.assertNotContains(response, 'add-document-btn')
        self.assertNotContains(response, 'Missing Requirements')
        self.assertNotContains(response, 'Version History')

        self.client.force_login(self.program_head)
        program_response = self.client.get(
            reverse('accreditation:submission_workspace_subarea', args=[self.area.slug, '1-1']),
        )
        self.assertContains(program_response, 'Missing Requirements')
        self.assertContains(program_response, 'Version History')

    def test_my_tasks_landing_shows_assigned_and_missing_instead_of_subareas(self):
        self.client.force_login(self.program_head)

        response = self.client.get(reverse('accreditation:submission_workspace'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'My Tasks')
        self.assertContains(response, 'Assigned')
        self.assertContains(response, 'Missing')
        self.assertContains(response, 'Deadline:')
        self.assertNotContains(response, 'Sub-Areas')

    def test_workspace_submit_button_uses_the_workflow_service(self):
        submission = self.make_submission()
        submission.self_evaluation = 'Prepared self evaluation'
        submission.actual_situation = 'Prepared actual situation'
        submission.save(update_fields=['self_evaluation', 'actual_situation', 'last_updated'])
        version = EvidenceVersion.objects.create(
            submission=submission,
            version_number=1,
            self_evaluation=submission.self_evaluation,
            actual_situation=submission.actual_situation,
            submitted_by=self.program_head,
        )
        EvidenceFile.objects.create(version=version, uploaded_by=self.program_head, link_url='https://example.com/evidence', original_name='evidence link')
        self.client.force_login(self.program_head)
        response = self.client.post(
            reverse('accreditation:submission_workspace_subarea', args=[self.area.slug, '1-1']),
            {'action': 'submit'},
        )
        self.assertRedirects(response, reverse('accreditation:submission_workspace_subarea', args=[self.area.slug, '1-1']))
        submission.refresh_from_db()
        self.assertEqual(submission.status, EvidenceSubmission.UNDER_DEAN_REVIEW)

    def test_qa_can_assign_area_to_all_departments_and_notify_program_heads(self):
        self.client.force_login(self.qa)
        deadline = timezone.localdate() + timedelta(days=21)

        response = self.client.post(
            reverse('accreditation:area_details', args=[self.area.slug]),
            {
                'department_scope': 'all',
                'deadline': deadline.isoformat(),
                'instructions': 'Upload the approved evidence before the checkpoint.',
            },
        )

        self.assertRedirects(response, reverse('accreditation:area_details', args=[self.area.slug]))
        self.assertEqual(AreaAssignment.objects.filter(area=self.area).count(), 2)
        assignment = AreaAssignment.objects.get(area=self.area, department=self.program)
        self.assertEqual(assignment.deadline, deadline)
        self.assertEqual(assignment.assigned_by, self.qa)
        self.assertTrue(Notification.objects.filter(user=self.program_head, kind='assignment').exists())
        self.assertTrue(AuditLog.objects.filter(action='AREA_ASSIGNED', object_type='AreaAssignment').exists())
        detail_response = self.client.get(reverse('accreditation:area_details', args=[self.area.slug]))
        self.assertContains(detail_response, 'Assign Area')
        self.assertContains(detail_response, 'data-assignment-toggle')
        self.assertContains(detail_response, 'role="dialog"')
        self.assertContains(detail_response, 'data-assignment-close')
        self.assertNotContains(detail_response, '<details')
        self.assertContains(detail_response, 'Current assignments')
        self.assertContains(detail_response, deadline.strftime('%b %d, %Y'))

    def test_qa_can_assign_area_to_specific_department_only(self):
        self.client.force_login(self.qa)
        deadline = timezone.localdate() + timedelta(days=14)

        response = self.client.post(
            reverse('accreditation:area_details', args=[self.area.slug]),
            {
                'department_scope': 'specific',
                'departments': [str(self.program.pk)],
                'deadline': deadline.isoformat(),
            },
        )

        self.assertRedirects(response, reverse('accreditation:area_details', args=[self.area.slug]))
        self.assertEqual(AreaAssignment.objects.filter(area=self.area).count(), 1)
        self.assertTrue(AreaAssignment.objects.filter(area=self.area, department=self.program, deadline=deadline).exists())
        self.assertFalse(AreaAssignment.objects.filter(area=self.area, department=self.department).exists())

    def test_only_qa_or_administrators_can_assign_an_area(self):
        self.client.force_login(self.dean)

        response = self.client.post(
            reverse('accreditation:area_details', args=[self.area.slug]),
            {
                'department_scope': 'all',
                'deadline': (timezone.localdate() + timedelta(days=7)).isoformat(),
            },
        )
        self.assertEqual(response.status_code, 403)

        response = self.client.get(reverse('accreditation:area_details', args=[self.area.slug]))
        self.assertNotContains(response, 'Assign Area')

    def test_program_head_tasks_follow_assignment_scope_and_deadline(self):
        other_program = Department.objects.create(
            code='BUS-BSBA',
            name='Bachelor of Science in Business Administration',
            kind=Department.PROGRAM,
        )
        deadline = timezone.localdate() + timedelta(days=30)
        self.client.force_login(self.qa)
        self.client.post(
            reverse('accreditation:area_details', args=[self.area.slug]),
            {
                'department_scope': 'specific',
                'departments': [str(other_program.pk)],
                'deadline': deadline.isoformat(),
                'instructions': 'Business program instructions',
            },
        )

        self.client.force_login(self.program_head)
        response = self.client.get(reverse('accreditation:submission_workspace'))
        self.assertContains(response, 'You have no assigned evidence tasks right now.')
        self.assertContains(response, 'No missing evidence requirements.')

        self.client.force_login(self.qa)
        self.client.post(
            reverse('accreditation:area_details', args=[self.area.slug]),
            {
                'department_scope': 'specific',
                'departments': [str(self.program.pk)],
                'deadline': deadline.isoformat(),
                'instructions': 'Upload the signed mission evidence.',
            },
        )
        self.client.force_login(self.program_head)
        response = self.client.get(reverse('accreditation:submission_workspace'))
        self.assertContains(response, deadline.strftime('%b %d, %Y'))
        self.assertContains(response, 'Upload the signed mission evidence.')
