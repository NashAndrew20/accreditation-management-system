from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import (
    Department,
    Policy,
    PolicyConsent,
    Role,
    RoleAssignment,
    UserProfile,
)


def make_approved_user(username='tester', password='safe-test-password'):
    user = get_user_model().objects.create_user(username=username, password=password)
    role = Role.objects.create(code='PROGRAM_HEAD', name='Program Head')
    department = Department.objects.create(code='COMP', name='College of Computing')
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


def active_policy(slug):
    return Policy.objects.get(slug=slug, status=Policy.ACTIVE)


def accept_payload():
    payload = {'acknowledge': '1', 'next': '/'}
    for policy in Policy.active_required():
        payload[f'version_{policy.policy_type}'] = policy.version
    return payload


@override_settings(POLICY_CONSENT_ENABLED=True)
class ConsentGateTests(TestCase):
    def test_approved_user_without_consent_is_redirected_from_dashboard(self):
        user = make_approved_user()
        self.client.force_login(user)

        response = self.client.get(reverse('dashboard:index'))

        self.assertRedirects(
            response,
            f"{reverse('core:consent')}?next=/",
            fetch_redirect_response=False,
        )

    def test_deep_protected_url_cannot_bypass_consent_gate(self):
        user = make_approved_user('bypasser')
        self.client.force_login(user)

        for url in (
            reverse('core:notifications'),
            reverse('accounts:settings_profile'),
            reverse('resources:document_repository'),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertRedirects(
                    response,
                    f"{reverse('core:consent')}?next={url}",
                    fetch_redirect_response=False,
                    target_status_code=302,
                )

    def test_anonymous_user_is_not_pushed_to_consent_screen(self):
        response = self.client.get(reverse('dashboard:index'))

        self.assertEqual(response.status_code, 302)
        self.assertNotIn(reverse('core:consent'), response.url)

    def test_pending_user_keeps_existing_approval_redirect_flow(self):
        user = make_approved_user('pending-user')
        user.profile.approval_status = UserProfile.PENDING
        user.profile.save(update_fields=['approval_status'])
        self.client.force_login(user)

        response = self.client.get(reverse('dashboard:index'))

        self.assertNotIn(reverse('core:consent'), response.url)

    def test_missing_consent_blocks_api_with_403_json(self):
        user = make_approved_user('api-user')
        self.client.force_login(user)

        response = self.client.get(reverse('api_auth:me'))

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response['Content-Type'].split(';')[0], 'application/json')

    def test_consent_screen_renders_policies_and_disabled_continue(self):
        user = make_approved_user('viewer')
        self.client.force_login(user)

        response = self.client.get(reverse('core:consent'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/consent.html')
        self.assertContains(response, 'Data Privacy Notice &amp; Policy')
        self.assertContains(response, 'Terms of Use')
        self.assertContains(response, 'data-consent-submit')
        self.assertContains(response, 'disabled')

    def test_policy_detail_is_public_and_versioned(self):
        privacy = active_policy('privacy-policy')
        response = self.client.get(reverse('core:policy_detail', args=['privacy-policy']))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'Version {privacy.version}')

        terms = active_policy('terms-of-use')
        response = self.client.get(reverse('core:policy_detail', args=['terms-of-use']))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, terms.title)

    def test_unknown_policy_slug_returns_404(self):
        response = self.client.get(reverse('core:policy_detail', args=['no-such-policy']))
        self.assertEqual(response.status_code, 404)


@override_settings(POLICY_CONSENT_ENABLED=True)
class ConsentAcceptTests(TestCase):
    def test_wrong_versions_are_rejected_server_side(self):
        user = make_approved_user('wrong-version')
        self.client.force_login(user)

        payload = accept_payload()
        payload['version_TERMS'] = '9.9'
        self.client.post(reverse('core:consent_accept'), payload)

        self.assertEqual(PolicyConsent.objects.filter(user=user).count(), 0)

    def test_missing_acknowledge_flag_is_rejected(self):
        user = make_approved_user('no-check')
        self.client.force_login(user)

        payload = accept_payload()
        payload['acknowledge'] = '0'
        self.client.post(reverse('core:consent_accept'), payload)

        self.assertEqual(PolicyConsent.objects.filter(user=user).count(), 0)

    def test_valid_accept_records_consents_and_unlocks_access(self):
        user = make_approved_user('accepting')
        self.client.force_login(user)

        response = self.client.post(reverse('core:consent_accept'), accept_payload())

        self.assertEqual(response.status_code, 302)
        consents = PolicyConsent.objects.filter(user=user)
        self.assertEqual(consents.count(), Policy.active_required().count())
        self.assertEqual(
            {c.policy.policy_type: c.version for c in consents},
            {p.policy_type: p.version for p in Policy.active_required()},
        )

        dashboard = self.client.get(reverse('dashboard:index'))
        self.assertEqual(dashboard.status_code, 200)

    def test_consent_persists_across_sessions_server_side(self):
        user = make_approved_user('re-login')
        self.client.force_login(user)
        self.client.post(reverse('core:consent_accept'), accept_payload())
        self.client.logout()

        self.assertTrue(self.client.login(username='re-login', password='safe-test-password'))
        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response.status_code, 200)

    def test_policy_update_requires_re_acknowledgment(self):
        user = make_approved_user('updater')
        self.client.force_login(user)
        self.client.post(reverse('core:consent_accept'), accept_payload())

        privacy = active_policy('privacy-policy')
        Policy.objects.filter(pk=privacy.pk).update(version='1.1')

        response = self.client.get(reverse('dashboard:index'))
        self.assertRedirects(
            response,
            f"{reverse('core:consent')}?next=/",
            fetch_redirect_response=False,
        )

    def test_settings_privacy_tab_shows_acknowledgment_history(self):
        user = make_approved_user('settings-user')
        self.client.force_login(user)
        self.client.post(reverse('core:consent_accept'), accept_payload())

        response = self.client.get(reverse('accounts:settings_profile'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Privacy &amp; Legal')
        self.assertContains(response, 'Data Privacy Notice &amp; Policy')
        self.assertContains(response, 'Acknowledgment History')


@override_settings(POLICY_CONSENT_ENABLED=False)
class ConsentDisabledTests(TestCase):
    def test_gate_is_bypassed_when_enforcement_is_off(self):
        user = make_approved_user('bypassed')
        self.client.force_login(user)

        response = self.client.get(reverse('dashboard:index'))

        self.assertEqual(response.status_code, 200)