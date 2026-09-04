from django.conf import settings
from django.http import HttpResponse, JsonResponse

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
