from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from unittest.mock import patch

from core.models import Department, Role, RoleAssignment, UserProfile


class LoginPageTests(TestCase):
    def setUp(self):
        cache.clear()
        self.role = Role.objects.create(code='PROGRAM_HEAD', name='Program Head')
        self.department = Department.objects.create(code='TEST', name='Test Program', kind=Department.PROGRAM)
        self.user = get_user_model().objects.create_user(
            username='qa-admin',
            email='qa-admin@jmcfi.edu.ph',
            password='safe-test-password',
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            department=self.department,
            approval_status=UserProfile.APPROVED,
        )
        self.assignment = RoleAssignment.objects.create(
            user=self.user,
            role=self.role,
            department=self.department,
            is_approved=True,
        )
        self.profile.active_assignment = self.assignment
        self.profile.save(update_fields=['active_assignment'])

    def test_login_page_renders(self):
        response = self.client.get(reverse('login'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/login.html')

    def test_login_assets_and_theme_toggle_are_available_on_dashboard(self):
        login_response = self.client.get(reverse('login'))

        self.assertContains(login_response, "js/theme.js")
        self.assertContains(login_response, "css/theme.css")
        self.assertContains(login_response, "login-auth-tabs")
        self.assertContains(login_response, "Continue with Google")
        self.assertNotContains(login_response, "data-theme-toggle")

        self.client.force_login(self.user)
        dashboard_response = self.client.get(reverse('dashboard:index'))

        self.assertContains(dashboard_response, "js/theme.js")
        self.assertContains(dashboard_response, "css/theme.css")
        self.assertContains(dashboard_response, "data-theme-toggle")

    def test_valid_credentials_redirect_to_dashboard(self):
        response = self.client.post(
            reverse('login'),
            {
                'username': self.user.username,
                'password': 'safe-test-password',
            },
        )

        self.assertRedirects(response, reverse('dashboard:index'))

    def test_profile_menu_contains_sign_out_without_topbar_account_actions(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('dashboard:index'))

        self.assertContains(response, 'data-profile-menu')
        self.assertContains(response, 'data-profile-popover')
        self.assertContains(response, 'profile-menu-action')
        self.assertContains(response, 'Sign out')
        self.assertNotContains(response, 'Switch Role')
        self.assertNotContains(response, 'Switch Account')

    def test_email_credentials_redirect_to_dashboard(self):
        response = self.client.post(
            reverse('login'),
            {
                'username': self.user.email,
                'password': 'safe-test-password',
            },
        )

        self.assertRedirects(response, reverse('dashboard:index'))

    def test_role_selection_rejects_external_redirect_target(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('accounts:select_role'),
            {
                'assignment': self.assignment.pk,
                'next': 'https://evil.example/steal-session',
            },
        )

        self.assertRedirects(response, reverse('dashboard:index'))

    def test_role_selection_allows_same_host_redirect_target(self):
        self.client.force_login(self.user)
        next_url = reverse('dashboard:index')

        response = self.client.post(
            reverse('accounts:select_role'),
            {'assignment': self.assignment.pk, 'next': next_url},
        )

        self.assertRedirects(response, next_url)

    def test_registration_creates_pending_account_and_assignment(self):
        response = self.client.post(reverse('register'), {
            'username': 'new-program-head',
            'email': 'new-program-head@jmcfi.edu.ph',
            'first_name': 'New',
            'last_name': 'Head',
            'role': self.role.id,
            'department': self.department.id,
            'password1': 'A-strong-registration-password-55!',
            'password2': 'A-strong-registration-password-55!',
        })
        self.assertEqual(response.status_code, 200)
        new_user = get_user_model().objects.get(username='new-program-head')
        self.assertFalse(new_user.is_active)
        self.assertEqual(new_user.profile.approval_status, UserProfile.PENDING)
        self.assertFalse(new_user.role_assignments.get().is_approved)

    def test_admin_can_approve_pending_account(self):
        admin_role = Role.objects.create(code='ADMIN', name='Admin')
        admin = get_user_model().objects.create_user(username='admin-user', password='admin-password')
        admin_profile = UserProfile.objects.create(
            user=admin,
            department=self.department,
            approval_status=UserProfile.APPROVED,
        )
        admin_assignment = RoleAssignment.objects.create(
            user=admin,
            role=admin_role,
            department=self.department,
            is_approved=True,
        )
        admin_profile.active_assignment = admin_assignment
        admin_profile.save(update_fields=['active_assignment'])
        pending = get_user_model().objects.create_user(username='pending-user', password='pending-password', is_active=False)
        pending_profile = UserProfile.objects.create(
            user=pending,
            department=self.department,
            approval_status=UserProfile.PENDING,
        )
        RoleAssignment.objects.create(user=pending, role=self.role, department=self.department, is_approved=False)

        self.client.force_login(admin)
        response = self.client.post(reverse('accounts:user_management'), {'action': 'approve', 'user_id': pending.id})
        self.assertRedirects(response, reverse('accounts:user_management'))
        pending.refresh_from_db()
        pending_profile.refresh_from_db()
        self.assertTrue(pending.is_active)
        self.assertEqual(pending_profile.approval_status, UserProfile.APPROVED)
        self.assertTrue(pending.role_assignments.get().is_approved)

    def test_user_management_hides_retired_demo_accounts_but_keeps_real_accounts(self):
        retired_demo = get_user_model().objects.create_user(
            username='legacy-demo',
            first_name='Legacy',
            last_name='Demo',
            password='legacy-password',
            is_active=False,
        )
        UserProfile.objects.create(
            user=retired_demo,
            department=self.department,
            approval_status=UserProfile.REJECTED,
            is_demo_account=True,
        )

        qa_role = Role.objects.create(code='QA', name='QA')
        qa = get_user_model().objects.create_user(username='qa-reviewer', password='qa-password')
        qa_profile = UserProfile.objects.create(
            user=qa,
            department=self.department,
            approval_status=UserProfile.APPROVED,
        )
        qa_assignment = RoleAssignment.objects.create(
            user=qa,
            role=qa_role,
            department=self.department,
            is_approved=True,
        )
        qa_profile.active_assignment = qa_assignment
        qa_profile.save(update_fields=['active_assignment'])

        self.client.force_login(qa)
        response = self.client.get(reverse('accounts:user_management'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'qa-admin')
        self.assertNotContains(response, 'Legacy Demo')
        self.assertNotContains(response, 'legacy-demo')

    def test_profile_settings_are_saved_to_database(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('accounts:settings_profile'), {
            'first_name': 'Updated',
            'last_name': 'User',
            'email': 'updated@jmcfi.edu.ph',
        })
        self.assertRedirects(response, reverse('accounts:settings_profile'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.get_full_name(), 'Updated User')
        self.assertEqual(self.user.email, 'updated@jmcfi.edu.ph')

    def test_jwt_token_and_refresh_endpoints_work_for_approved_users(self):
        api_client = APIClient()
        token_response = api_client.post(reverse('api_auth:token'), {
            'username': self.user.username,
            'password': 'safe-test-password',
        }, format='json')

        self.assertEqual(token_response.status_code, 200)
        self.assertIn('access', token_response.data)
        self.assertIn('refresh', token_response.data)
        self.assertEqual(token_response.data['user']['username'], self.user.username)

        refresh_response = api_client.post(reverse('api_auth:token_refresh'), {
            'refresh': token_response.data['refresh'],
        }, format='json')
        self.assertEqual(refresh_response.status_code, 200)
        self.assertIn('access', refresh_response.data)

    def test_jwt_protected_api_requires_bearer_token_and_keeps_session_separate(self):
        api_client = APIClient()
        me_url = reverse('api_auth:me')

        missing_token_response = api_client.get(me_url)
        self.assertEqual(missing_token_response.status_code, 401)
        self.assertIn('Bearer', missing_token_response.headers.get('WWW-Authenticate', ''))

        self.assertTrue(api_client.login(username=self.user.username, password='safe-test-password'))
        session_only_response = api_client.get(me_url)
        self.assertEqual(session_only_response.status_code, 401)

        token_response = api_client.post(reverse('api_auth:token'), {
            'username': self.user.email,
            'password': 'safe-test-password',
        }, format='json')
        self.assertEqual(token_response.status_code, 200)
        api_client.logout()
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_response.data['access']}")
        authenticated_response = api_client.get(me_url)

        self.assertEqual(authenticated_response.status_code, 200)
        self.assertEqual(authenticated_response.data['username'], self.user.username)
        self.assertEqual(authenticated_response.data['active_role'], 'Program Head')

    def test_website_login_is_rate_limited_by_ip(self):
        login_url = reverse('login')
        credentials = {'username': 'not-a-user', 'password': 'wrong-password'}

        for _ in range(5):
            response = self.client.post(login_url, credentials)
            self.assertNotEqual(response.status_code, 429)

        response = self.client.post(login_url, credentials)

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers['Retry-After'], '60')

    def test_api_token_login_is_rate_limited_by_ip(self):
        token_url = reverse('api_auth:token')
        credentials = {'username': 'not-a-user', 'password': 'wrong-password'}
        api_client = APIClient()

        for _ in range(5):
            response = api_client.post(token_url, credentials, format='json')
            self.assertNotEqual(response.status_code, 429)

        response = api_client.post(token_url, credentials, format='json')

        self.assertEqual(response.status_code, 429)
        retry_after = int(response.headers['Retry-After'])
        self.assertGreaterEqual(retry_after, 1)
        self.assertLessEqual(retry_after, 60)


class GoogleLoginTests(LoginPageTests):
    google_settings = {
        'GOOGLE_OAUTH_ENABLED': True,
        'GOOGLE_OAUTH_CLIENT_ID': 'test-client-id.apps.googleusercontent.com',
        'GOOGLE_OAUTH_CLIENT_SECRET': 'test-client-secret',
        'GOOGLE_OAUTH_REDIRECT_URI': 'http://testserver/login/google/callback/',
        'GOOGLE_OAUTH_ALLOWED_DOMAIN': '',
    }

    @override_settings(**google_settings)
    def test_google_login_start_redirects_to_google_with_state_and_nonce(self):
        response = self.client.get(reverse('google_login'))

        self.assertEqual(response.status_code, 302)
        self.assertIn('accounts.google.com/o/oauth2/v2/auth', response['Location'])
        session = self.client.session
        self.assertTrue(session.get('google_oauth_state'))
        self.assertTrue(session.get('google_oauth_nonce'))

    @override_settings(**google_settings)
    @patch('accounts.google_oauth.verify_id_token')
    @patch('accounts.google_oauth.exchange_code')
    def test_google_callback_links_approved_account_and_creates_session(
        self,
        exchange_code,
        verify_id_token,
    ):
        session = self.client.session
        session['google_oauth_state'] = 'state-value'
        session['google_oauth_nonce'] = 'nonce-value'
        session['google_oauth_next'] = reverse('dashboard:index')
        session.save()
        exchange_code.return_value = {'id_token': 'verified-id-token'}
        verify_id_token.return_value = {
            'sub': 'google-subject-123',
            'email': self.user.email,
            'email_verified': True,
        }

        response = self.client.get(
            reverse('google_login_callback'),
            {'state': 'state-value', 'code': 'one-time-code'},
        )

        self.assertRedirects(response, reverse('dashboard:index'))
        self.assertEqual(self.client.session.get('_auth_user_id'), str(self.user.pk))
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.google_subject, 'google-subject-123')
        exchange_code.assert_called_once_with(
            'one-time-code',
            'http://testserver/login/google/callback/',
        )
        verify_id_token.assert_called_once_with('verified-id-token', 'nonce-value')

    @override_settings(**google_settings)
    def test_google_callback_rejects_invalid_state(self):
        session = self.client.session
        session['google_oauth_state'] = 'expected-state'
        session['google_oauth_nonce'] = 'nonce-value'
        session.save()

        response = self.client.get(
            reverse('google_login_callback'),
            {'state': 'different-state', 'code': 'one-time-code'},
        )

        self.assertRedirects(response, reverse('login'))
        self.assertNotIn('_auth_user_id', self.client.session)
