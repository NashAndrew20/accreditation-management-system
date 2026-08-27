import hashlib

from django.core.cache import cache


LOGIN_ATTEMPT_LIMIT = 5
LOGIN_ATTEMPT_WINDOW = 60


def _client_ip(request):
    """Use the direct peer address unless a trusted proxy is configured."""
    return request.META.get('REMOTE_ADDR') or 'unknown'


def _login_cache_key(request):
    client_ip = _client_ip(request).encode('utf-8')
    ip_digest = hashlib.sha256(client_ip).hexdigest()
    return f'jmcfi-ams:login-attempts:{ip_digest}'


def allow_login_attempt(request):
    """Allow up to five login POSTs per IP in a one-minute window."""
    cache_key = _login_cache_key(request)
    if cache.add(cache_key, 1, timeout=LOGIN_ATTEMPT_WINDOW):
        return True

    try:
        attempt_count = cache.incr(cache_key)
    except ValueError:
        # The key may expire between add() and incr(); start a fresh window.
        cache.set(cache_key, 1, timeout=LOGIN_ATTEMPT_WINDOW)
        return True
    return attempt_count <= LOGIN_ATTEMPT_LIMIT
