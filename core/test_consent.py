from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.timezone import now

from core import consent as consent_service
from core.models import (
    CookiePreference,
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
        self.assertTemplateUsed(response, 'core/consent_overlay.html')
        self.assertTemplateUsed(response, 'accounts/login.html')
        self.assertContains(response, 'Review before accessing the AMS')
        self.assertContains(response, 'Institutional Policies')
        self.assertContains(response, 'Data Privacy Notice &amp; Policy')
        self.assertContains(response, 'Terms of Use')
        self.assertContains(response, 'consent-overlay')
        self.assertContains(response, 'data-consent-submit')
        self.assertContains(response, 'disabled')
        # The consent dialog overlays the login form on the same page.
        self.assertContains(response, 'login-form')
        self.assertContains(response, 'login-panel')
        self.assertNotContains(response, 'consent-page')

    def test_policy_detail_is_public_and_versioned(self):
        privacy = active_policy('privacy-policy')
        response = self.client.get(reverse('core:policy_detail', args=['privacy-policy']))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'Version {privacy.version}')

        terms = active_policy('terms-of-use')
        response = self.client.get(reverse('core:policy_detail', args=['terms-of-use']))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, terms.title)

    def test_consent_screen_lists_required_cookie_policy(self):
        user = make_approved_user('cookie-viewer')
        self.client.force_login(user)

        response = self.client.get(reverse('core:consent'))

        self.assertContains(response, 'Cookies')
        self.assertContains(response, 'Cookie Policy')
        self.assertContains(response, 'Effective ')
        for policy in Policy.active_required():
            with self.subTest(policy=policy.slug):
                self.assertContains(response, f'version_{policy.policy_type}')

    def test_consent_intro_uses_authenticated_display_name(self):
        user = make_approved_user('named-user')
        user.first_name = 'Marisol'
        user.last_name = 'Garcia'
        user.save(update_fields=['first_name', 'last_name'])
        self.client.force_login(user)

        response = self.client.get(reverse('core:consent'))

        self.assertContains(response, 'Marisol Garcia')

    def test_consent_intro_falls_back_to_username(self):
        user = make_approved_user('just-a-username')
        user.first_name = ''
        user.last_name = ''
        user.save(update_fields=['first_name', 'last_name'])
        self.client.force_login(user)

        response = self.client.get(reverse('core:consent'))

        self.assertContains(response, 'just-a-username')

    def test_consent_cards_show_clean_summary_not_history_clutter(self):
        user = make_approved_user('clean-cards')
        self.client.force_login(user)
        self.client.post(reverse('core:consent_accept'), accept_payload())
        privacy = active_policy('privacy-policy')
        Policy.objects.filter(pk=privacy.pk).update(version='1.1')

        response = self.client.get(reverse('core:consent'))

        self.assertContains(response, 'I confirm that I have reviewed the institutional policies')
        # History details live on the settings page, not the access screen.
        self.assertNotContains(response, 'Previously acknowledged')
        self.assertNotContains(response, 'Updated ')
        self.assertNotContains(response, 'Updated September')

    def test_cookie_and_aira_policy_pages_render_publicly(self):
        cookie = active_policy('cookie-policy')
        aira = active_policy('aira-data-notice')

        cookie_response = self.client.get(reverse('core:policy_detail', args=['cookie-policy']))
        self.assertEqual(cookie_response.status_code, 200)
        self.assertTemplateUsed(cookie_response, 'core/policies/cookie_policy.html')
        self.assertContains(cookie_response, cookie.title)
        self.assertContains(cookie_response, f'Version {cookie.version}')

        aira_response = self.client.get(reverse('core:policy_detail', args=['aira-data-notice']))
        self.assertEqual(aira_response.status_code, 200)
        self.assertTemplateUsed(aira_response, 'core/policies/aira_notice.html')
        self.assertContains(aira_response, 'AIRA &amp; AI Data-Use Notice')

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


@override_settings(POLICY_CONSENT_ENABLED=True)
class CookiePreferenceTests(TestCase):
    def test_preferences_are_persisted_server_side(self):
        user = make_approved_user('cookie-user')
        self.client.force_login(user)
        self.client.post(reverse('core:consent_accept'), accept_payload())

        response = self.client.post(reverse('core:cookie_preferences'), {'next': '/'})

        self.assertRedirects(response, '/', fetch_redirect_response=False)
        preference = CookiePreference.objects.get(user=user)
        self.assertTrue(preference.essential_cookies_accepted)
        self.assertEqual(preference.optional_cookies, {})

    @override_settings(COOKIE_OPTIONAL_CATEGORIES=['analytics', 'preferences'])
    def test_unknown_categories_are_never_accepted(self):
        user = make_approved_user('cookie-unknown')
        self.client.force_login(user)
        self.client.post(reverse('core:consent_accept'), accept_payload())

        self.client.post(
            reverse('core:cookie_preferences'),
            {'optional_cookies': ['analytics', 'spyware'], 'next': '/'},
        )

        preference = CookiePreference.objects.get(user=user)
        self.assertTrue(preference.optional_cookies.get('analytics'))
        self.assertNotIn('spyware', preference.optional_cookies)

    def test_unacknowledged_user_cannot_save_preferences(self):
        user = make_approved_user('cookie-gated')
        self.client.force_login(user)

        response = self.client.post(reverse('core:cookie_preferences'), {'next': '/'})

        self.assertFalse(CookiePreference.objects.filter(user=user).exists())
        self.assertEqual(response.status_code, 302)


@override_settings(POLICY_CONSENT_ENABLED=True)
class ConsentWithdrawTests(TestCase):
    def test_withdraw_non_required_policy_marks_revoked(self):
        user = make_approved_user('withdrawer')
        self.client.force_login(user)
        self.client.post(reverse('core:consent_accept'), accept_payload())
        aira = active_policy('aira-data-notice')
        consent_service.acknowledge(user, aira, aira.version)
        accepted = PolicyConsent.objects.get(user=user, policy=aira, status=PolicyConsent.ACCEPTED)

        response = self.client.post(reverse('core:consent_withdraw'), {'policy_id': aira.pk})

        self.assertRedirects(response, reverse('accounts:settings_profile'))
        accepted.refresh_from_db()
        self.assertEqual(accepted.status, PolicyConsent.REVOKED)
        self.assertIsNotNone(accepted.withdrawn_at)
        dashboard = self.client.get(reverse('dashboard:index'))
        self.assertEqual(dashboard.status_code, 200)

    def test_withdraw_required_policy_is_rejected(self):
        user = make_approved_user('no-withdraw-required')
        self.client.force_login(user)
        self.client.post(reverse('core:consent_accept'), accept_payload())
        privacy = active_policy('privacy-policy')

        response = self.client.post(reverse('core:consent_withdraw'), {'policy_id': privacy.pk})

        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            PolicyConsent.objects.filter(
                user=user, policy=privacy, status=PolicyConsent.ACCEPTED,
            ).exists(),
        )

    def test_withdraw_rerequires_acknowledgment_after_policy_becomes_required(self):
        user = make_approved_user('re-required')
        self.client.force_login(user)
        aira = active_policy('aira-data-notice')
        consent_service.acknowledge(user, aira, aira.version)
        PolicyConsent.objects.filter(user=user, policy=aira, status=PolicyConsent.ACCEPTED).update(
            status=PolicyConsent.REVOKED,
            withdrawn_at=now(),
        )

        Policy.objects.filter(pk=aira.pk).update(is_required=True)
        try:
            response = self.client.get(reverse('dashboard:index'))
            self.assertRedirects(
                response,
                f"{reverse('core:consent')}?next=/",
                fetch_redirect_response=False,
            )
        finally:
            Policy.objects.filter(pk=aira.pk).update(is_required=False)