import hmac
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token


GOOGLE_AUTHORIZATION_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'


class GoogleOAuthError(Exception):
    """Raised when Google's authentication response cannot be trusted."""


def build_authorization_url(state, nonce, redirect_uri):
    """Build the Google authorization-code request without exposing secrets."""
    params = {
        'client_id': settings.GOOGLE_OAUTH_CLIENT_ID,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': 'openid email profile',
        'state': state,
        'nonce': nonce,
        'prompt': 'select_account',
    }
    return f'{GOOGLE_AUTHORIZATION_URL}?{urlencode(params)}'


def exchange_code(code, redirect_uri):
    """Exchange Google's one-time authorization code for an ID token."""
    payload = urlencode({
        'code': code,
        'client_id': settings.GOOGLE_OAUTH_CLIENT_ID,
        'client_secret': settings.GOOGLE_OAUTH_CLIENT_SECRET,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code',
    }).encode('utf-8')
    request = Request(
        GOOGLE_TOKEN_URL,
        data=payload,
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        method='POST',
    )
    try:
        with urlopen(request, timeout=10) as response:
            response_body = response.read()
    except (HTTPError, URLError, TimeoutError) as error:
        raise GoogleOAuthError('Google token exchange failed.') from error

    try:
        token_data = json.loads(response_body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise GoogleOAuthError('Google returned an invalid token response.') from error
    if not isinstance(token_data, dict) or not token_data.get('id_token'):
        raise GoogleOAuthError('Google did not return an ID token.')
    return token_data


def verify_id_token(raw_token, expected_nonce):
    """Verify the ID token signature, audience, expiry, nonce, and email."""
    try:
        claims = id_token.verify_oauth2_token(
            raw_token,
            google_requests.Request(),
            settings.GOOGLE_OAUTH_CLIENT_ID,
        )
    except ValueError as error:
        raise GoogleOAuthError('Google returned an invalid identity token.') from error

    token_nonce = claims.get('nonce', '')
    if not isinstance(token_nonce, str) or not hmac.compare_digest(token_nonce, expected_nonce):
        raise GoogleOAuthError('Google identity verification failed.')
    if claims.get('email_verified') is not True:
        raise GoogleOAuthError('The Google email address is not verified.')

    email = claims.get('email', '')
    subject = claims.get('sub', '')
    if not isinstance(email, str) or not email.strip() or not isinstance(subject, str) or not subject:
        raise GoogleOAuthError('Google did not return a usable account.')

    allowed_domain = settings.GOOGLE_OAUTH_ALLOWED_DOMAIN.strip().lower()
    hosted_domain = claims.get('hd', '')
    if (
        allowed_domain
        and (
            not isinstance(hosted_domain, str)
            or hosted_domain.strip().lower() != allowed_domain
        )
    ):
        raise GoogleOAuthError('This Google account is outside the allowed organization.')

    return {
        'sub': subject,
        'email': email.strip().lower(),
        'first_name': str(claims.get('given_name', '')).strip(),
        'last_name': str(claims.get('family_name', '')).strip(),
    }
