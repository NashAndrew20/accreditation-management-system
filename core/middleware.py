from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse

from .consent import consent_enabled, has_current_consent
from .access import is_approved_user
from .rate_limit import allow_request


class RequestRateLimitMiddleware:
    """Protect dynamic application requests from excessive IP traffic."""

    EXCLUDED_PREFIXES = ('/static/', '/media/')

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._should_limit(request) and not allow_request(request):
            return self._too_many_requests(request)
        return self.get_response(request)

    @classmethod
    def _should_limit(cls, request):
        return (
            request.method != 'OPTIONS'
            and not request.path_info.startswith(cls.EXCLUDED_PREFIXES)
        )

    @staticmethod
    def _too_many_requests(request):
        message = 'Too many requests. Please try again in about one minute.'
        if request.path_info.startswith('/api/'):
            response = JsonResponse({'detail': message}, status=429)
        else:
            response = HttpResponse(message, status=429, content_type='text/plain')
        response['Retry-After'] = str(settings.REQUEST_RATE_WINDOW_SECONDS)
        response['Cache-Control'] = 'no-store'
        return response


class ConsentGateMiddleware:
    """Gate authenticated AMS access until current policies are acknowledged.

    Bypass-proof by design: any authenticated request to a protected URL is
    redirected to the consent screen until explicit, versioned consent records
    exist for every active required policy.
    """

    EXCLUDED_PREFIXES = (
        '/static/',
        '/media/',
        '/admin/',
        '/login/',
        '/logout/',
        '/register/',
        '/consent/',
        '/policies/',
        '/account/select-role/',
        '/account/change-password/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._should_redirect(request):
            if request.path_info.startswith('/api/'):
                return JsonResponse(
                    {'detail': 'Policy consent required before access.'},
                    status=403,
                )
            return redirect('{}?next={}'.format(
                reverse('core:consent'),
                request.path_info,
            ))
        return self.get_response(request)

    def _should_redirect(self, request):
        if not request.user.is_authenticated:
            return False
        # Only users who would otherwise reach the AMS need the consent gate;
        # pending/rejected users keep their existing approval redirect flow.
        if not (is_approved_user(request.user) or request.user.is_superuser):
            return False
        path = request.path_info
        if path.startswith(self.EXCLUDED_PREFIXES):
            return False
        if not consent_enabled():
            return False
        return not has_current_consent(request.user)
