from rest_framework.throttling import AnonRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    """Limit unauthenticated token requests by client IP."""

    scope = 'login'
