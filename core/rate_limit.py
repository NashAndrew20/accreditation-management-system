import hashlib

from django.conf import settings
from django.core.cache import cache


LOGIN_ATTEMPT_LIMIT = 5
LOGIN_ATTEMPT_WINDOW = 60
REQUEST_RATE_LIMIT = 120
REQUEST_RATE_WINDOW = 60
AIRA_REQUEST_LIMIT = 60
AIRA_REQUEST_WINDOW = 60


def _client_ip(request):
    """Use the direct peer address unless a trusted proxy is configured."""
    return request.META.get('REMOTE_ADDR') or 'unknown'


def _login_cache_key(request):
    return _ip_cache_key('login-attempts', request)


def _request_cache_key(request):
    return _ip_cache_key('request-rate', request)


def _aira_cache_key(user):
    user_digest = hashlib.sha256(str(user.pk).encode('utf-8')).hexdigest()
    return f'jmcfi-ams:aira-request:{user_digest}'


def _ip_cache_key(prefix, request):
    client_ip = _client_ip(request).encode('utf-8')
    ip_digest = hashlib.sha256(client_ip).hexdigest()
    return f'jmcfi-ams:{prefix}:{ip_digest}'


def _allow_counter(cache_key, limit, window):
    if cache.add(cache_key, 1, timeout=window):
        return True

    try:
        attempt_count = cache.incr(cache_key)
    except ValueError:
        # The key may expire between add() and incr(); start a fresh window.
        cache.set(cache_key, 1, timeout=window)
        return True
    return attempt_count <= limit


def allow_login_attempt(request):
    """Allow up to five login POSTs per IP in a one-minute window."""
    return _allow_counter(
        _login_cache_key(request),
        LOGIN_ATTEMPT_LIMIT,
        LOGIN_ATTEMPT_WINDOW,
    )


def allow_request(request):
    """Allow a reasonable number of dynamic requests from one client IP."""
    return _allow_counter(
        _request_cache_key(request),
        getattr(settings, 'REQUEST_RATE_LIMIT', REQUEST_RATE_LIMIT),
        getattr(settings, 'REQUEST_RATE_WINDOW_SECONDS', REQUEST_RATE_WINDOW),
    )


def allow_aira_request(user):
    """Limit how often one authenticated user may query AIRA."""
    return _allow_counter(
        _aira_cache_key(user),
        getattr(settings, 'AIRA_REQUEST_LIMIT', AIRA_REQUEST_LIMIT),
        getattr(settings, 'AIRA_REQUEST_WINDOW_SECONDS', AIRA_REQUEST_WINDOW),
    )
