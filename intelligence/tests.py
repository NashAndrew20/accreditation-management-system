from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accreditation.models import (
    AccreditationArea,
    AccreditationCycle,
    AccreditationLevel,
    EvidenceRequirement,
    EvidenceSubmission,
)
from core.models import Department, Role, RoleAssignment, UserProfile

class ReportsExportTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username='reports-admin',
            password='123',
            is_active=True,
        )
        role = Role.objects.create(code='ADMIN', name='Admin', is_internal=True, is_active=True)
        department = Department.objects.create(
            code='CIVIL',
            name='Civil Engineering',
            kind=Department.DEPARTMENT,
        )
        profile = UserProfile.objects.create(
            user=self.user,
            department=department,
            approval_status=UserProfile.APPROVED,
        )
        assignment = RoleAssignment.objects.create(
            user=self.user,
            role=role,
            department=department,
            is_approved=True,
        )
        profile.active_assignment = assignment
        profile.save(update_fields=['active_assignment'])

        cycle = AccreditationCycle.objects.create(
            name='PACUCOA Accreditation Cycle',
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
        requirement = EvidenceRequirement.objects.create(
            area=area,
            code='1.1',
            title='Mission and Vision',
        )
        EvidenceSubmission.objects.create(
            requirement=requirement,
            department=department,
            program_head=self.user,
            created_by=self.user,
            status=EvidenceSubmission.COMPLIED,
        )

    def test_export_returns_live_database_report_as_pdf(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('intelligence:reports_export'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment;', response['Content-Disposition'])
        self.assertTrue(response.content.startswith(b'%PDF-1.4'))
        self.assertIn(b'100%', response.content)
        self.assertIn(b'Civil Engineering', response.content)

    def test_smart_companion_uses_aira_image(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('intelligence:smart_companion'))

        self.assertContains(response, '/static/images/aira-wave-1.png')
        self.assertContains(response, 'data-aira-image="/static/images/aira-wave-1.png"')
        self.assertContains(response, 'alt="AIRA"')
        self.assertContains(response, '<h2>AIRA</h2>')
        self.assertContains(response, "Hello! I'm AIRA.")
        self.assertNotContains(response, 'JMCFI Accreditation Companion')
        self.assertNotContains(response, '<h1>Smart Companion</h1>')
