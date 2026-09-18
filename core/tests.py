from django.core.cache import cache
from django.test import TestCase, override_settings


class RequestRateLimitTests(TestCase):
    def setUp(self):
        cache.clear()

    @override_settings(REQUEST_RATE_LIMIT=2, REQUEST_RATE_WINDOW_SECONDS=60)
    def test_dynamic_requests_return_429_after_ip_limit(self):
        response = self.client.get('/login/')
        self.assertEqual(response.status_code, 200)

        response = self.client.get('/login/')
        self.assertEqual(response.status_code, 200)

        response = self.client.get('/login/')
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response['Retry-After'], '60')

    @override_settings(REQUEST_RATE_LIMIT=1, REQUEST_RATE_WINDOW_SECONDS=60)
    def test_static_assets_are_not_counted_by_server_limiter(self):
        self.client.get('/static/css/login.css')
        response = self.client.get('/login/')

        self.assertNotEqual(response.status_code, 429)


class ErrorHandlingViewsTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_permission_denied_403_renders_institutional_ui(self):
        from config.error_views import permission_denied
        from django.test import RequestFactory
        from django.core.exceptions import PermissionDenied

        factory = RequestFactory()
        request = factory.get('/accreditation/review/103/')
        from django.contrib.auth.models import AnonymousUser
        request.user = AnonymousUser()

        response = permission_denied(request, PermissionDenied('This review workspace is restricted to authorized users.'))
        self.assertEqual(response.status_code, 403)
        content = response.content.decode('utf-8')
        self.assertIn('Access Denied', content)
        self.assertIn('403', content)
        self.assertIn('Workflow Access Restriction', content)
        self.assertIn('This review workspace is restricted to authorized users.', content)
        self.assertIn('Return to Dashboard', content)
        self.assertIn('/static/images/jmcfi-logo.png', content)
        self.assertIn('/static/css/error.css', content)
        # Ensure raw diagnostics are never present
        self.assertNotIn('CSRF cookie not set', content)
        self.assertNotIn('Traceback', content)

    def test_csrf_failure_view_hides_cookie_diagnostics(self):
        from config.error_views import csrf_failure
        from django.test import RequestFactory
        from django.contrib.auth.models import AnonymousUser

        factory = RequestFactory()
        request = factory.post('/login/')
        request.user = AnonymousUser()

        response = csrf_failure(request, reason='CSRF cookie not set.')
        self.assertEqual(response.status_code, 403)
        content = response.content.decode('utf-8')
        self.assertIn('Access Denied', content)
        self.assertIn('Security Session Validation', content)
        self.assertIn('Your security session could not be validated', content)
        self.assertIn('Go to Login', content)
        self.assertIn('Home', content)
        # Verify internal raw reason is completely stripped from user view
        self.assertNotIn('CSRF cookie not set', content)

    def test_page_not_found_404_renders_institutional_ui(self):
        response = self.client.get('/this-path-definitely-does-not-exist-at-all/')
        self.assertEqual(response.status_code, 404)
        content = response.content.decode('utf-8')
        self.assertIn('Page Not Found', content)
        self.assertIn('404', content)
        self.assertIn('Navigation Notice', content)
        self.assertIn('Return to Dashboard', content)
        self.assertIn('Go Back', content)

    def test_server_error_500_renders_reference_id_and_try_again(self):
        from config.error_views import server_error
        from django.test import RequestFactory
        from django.contrib.auth.models import AnonymousUser

        factory = RequestFactory()
        request = factory.get('/broken-url/')
        request.user = AnonymousUser()

        response = server_error(request)
        self.assertEqual(response.status_code, 500)
        content = response.content.decode('utf-8')
        self.assertIn('Something Went Wrong', content)
        self.assertIn('500', content)
        self.assertIn('No changes were confirmed from this request', content)
        self.assertIn('Reference ID: AMS-', content)
        self.assertIn('Try Again', content)

    def test_bad_request_400_renders_institutional_ui(self):
        from config.error_views import bad_request
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get('/bad-request/')
        response = bad_request(request)
        self.assertEqual(response.status_code, 400)
        content = response.content.decode('utf-8')
        self.assertIn('Invalid Request', content)
        self.assertIn('400', content)
        self.assertIn('Return to Dashboard', content)

    def test_rate_limited_429_renders_institutional_ui(self):
        from config.error_views import rate_limited
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get('/rate-limited/')
        response = rate_limited(request, retry_after=60)
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response['Retry-After'], '60')
        content = response.content.decode('utf-8')
        self.assertIn('Too Many Requests', content)
        self.assertIn('429', content)
        self.assertIn('Rate Limit Notice', content)
        self.assertIn('Try Again Later', content)

    def test_generic_error_503_and_413(self):
        from config.error_views import generic_error
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get('/service-unavailable/')

        resp_503 = generic_error(request, 503)
        self.assertEqual(resp_503.status_code, 503)
        content_503 = resp_503.content.decode('utf-8')
        self.assertIn('Service Temporarily Unavailable', content_503)
        self.assertIn('503', content_503)
        self.assertIn('Try Again', content_503)

        resp_413 = generic_error(request, 413)
        self.assertEqual(resp_413.status_code, 413)
        content_413 = resp_413.content.decode('utf-8')
        self.assertIn('Upload Size Limit Exceeded', content_413)
        self.assertIn('413', content_413)
        self.assertIn('Choose Another File', content_413)

