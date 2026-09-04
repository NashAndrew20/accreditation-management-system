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
