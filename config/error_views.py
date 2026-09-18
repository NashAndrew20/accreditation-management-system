import logging
import uuid
from django.shortcuts import render
from django.utils import timezone

logger = logging.getLogger(__name__)


def _generate_reference_id():
    return f"AMS-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


def _is_safe_message(message):
    """Ensure raw tracebacks, SQL queries, or internal paths are never leaked."""
    if not message or not isinstance(message, str):
        return False
    lowered = message.lower()
    dangerous_keywords = (
        'traceback', 'exception', 'syntaxerror', 'operationalerror',
        'select ', 'insert ', 'update ', 'delete from', 'table ',
        'file "', 'line ', 'csrf cookie', 'django', 'backend', 'password', 'secret',
    )
    for kw in dangerous_keywords:
        if kw in lowered:
            return False
    return len(message.strip()) > 0 and len(message.strip()) < 300


def permission_denied(request, exception=None):
    return render(request, '403.html', status=403)
    """Handler for HTTP 403 Forbidden."""
    raw_message = str(exception) if exception else ''
    if _is_safe_message(raw_message):
        context_message = raw_message
    else:
        context_message = (
            'This review workspace is restricted to authorized users assigned '
            'to the corresponding accreditation workflow.'
        )

    is_authenticated = request.user.is_authenticated if hasattr(request, 'user') else False

    context = {
        'status_code': 403,
        'error_title': 'Access Denied',
        'error_description': (
            "You don't have permission to access this page with your current "
            "account or workflow role."
        ),
        'context_title': 'Workflow Access Restriction',
        'context_message': context_message,
        'icon_name': 'lock',
        'icon_tone': 'maroon',
        'primary_action_url': '/',
        'primary_action_label': 'Return to Dashboard',
        'primary_action_icon': 'home',
        'secondary_action_url': 'javascript:history.back()' if is_authenticated else '/login/',
        'secondary_action_label': 'Go Back' if is_authenticated else 'Sign In Again',
        'secondary_action_icon': 'arrow-left' if is_authenticated else 'lock',
    }
    return render(request, '403.html', context, status=403)


def csrf_failure(request, reason=''):
    """Custom CSRF failure handler.

    Logs the actual technical reason server-side and renders a professional,
    reassuring security session failure page without leaking internal cookie/token state.
    """
    path = getattr(request, 'path', 'unknown')
    user = getattr(request, 'user', 'anonymous')
    logger.warning('CSRF security check failed at %s for user %s: %s', path, user, reason)

    context = {
        'status_code': 403,
        'error_title': 'Access Denied',
        'error_description': (
            "You don't have permission to view this page, or your session security check failed. "
            "Contact your administrator if you believe this is a mistake."
        ),
        'context_title': 'Security Session Validation',
        'context_message': (
            'Your security session could not be validated. Please return to the login '
            'page and try again.'
        ),
        'icon_name': 'shield-alert',
        'icon_tone': 'maroon',
        'primary_action_url': '/login/',
        'primary_action_label': 'Go to Login',
        'primary_action_icon': 'arrow-right',
        'secondary_action_url': '/',
        'secondary_action_label': 'Home',
        'secondary_action_icon': 'home',
    }
    return render(request, '403.html', context, status=403)


def page_not_found(request, exception=None):
    return render(request, '404.html', status=404)
    """Handler for HTTP 404 Not Found."""
    context = {
        'status_code': 404,
        'error_title': 'Page Not Found',
        'error_description': (
            "The page you're looking for could not be found or may no longer be available."
        ),
        'context_title': 'Navigation Notice',
        'context_message': (
            'Please verify the destination address or navigate back to an authorized accreditation '
            'workspace. No changes were made to your records.'
        ),
        'icon_name': 'search',
        'icon_tone': 'slate',
        'primary_action_url': '/',
        'primary_action_label': 'Return to Dashboard',
        'primary_action_icon': 'home',
        'secondary_action_url': 'javascript:history.back()',
        'secondary_action_label': 'Go Back',
        'secondary_action_icon': 'arrow-left',
    }
    return render(request, '404.html', context, status=404)


def server_error(request):
    return render(request, '500.html', status=500)
    """Handler for HTTP 500 Server Error."""
    ref_id = _generate_reference_id()
    path = getattr(request, 'path', 'unknown')
    logger.error('Internal server error encountered [Ref: %s] at %s', ref_id, path, exc_info=True)

    context = {
        'status_code': 500,
        'error_title': 'Something Went Wrong',
        'error_description': (
            'The system encountered an unexpected problem while processing your request.'
        ),
        'context_title': 'Transaction Notice',
        'context_message': (
            'No changes were confirmed from this request. The incident has been recorded '
            'in the server logs for administrative review.'
        ),
        'reference_id': ref_id,
        'icon_name': 'server',
        'icon_tone': 'rose',
        'retry_action': True,
        'primary_action_url': '/',
        'primary_action_label': 'Return to Dashboard',
    }
    return render(request, '500.html', context, status=500)


def bad_request(request, exception=None):
    """Handler for HTTP 400 Bad Request."""
    context = {
        'status_code': 400,
        'error_title': 'Invalid Request',
        'error_description': (
            'The server could not process this request because it is malformed or contains invalid parameters.'
        ),
        'context_title': 'Request Notice',
        'context_message': (
            'Please verify the submitted information or return to the dashboard to continue your work.'
        ),
        'icon_name': 'alert',
        'icon_tone': 'gold',
        'primary_action_url': '/',
        'primary_action_label': 'Return to Dashboard',
        'primary_action_icon': 'home',
        'secondary_action_url': 'javascript:history.back()',
        'secondary_action_label': 'Go Back',
        'secondary_action_icon': 'arrow-left',
    }
    return render(request, 'error_generic.html', context, status=400)


def rate_limited(request, retry_after=60):
    """Handler for HTTP 429 Too Many Requests."""
    context = {
        'status_code': 429,
        'error_title': 'Too Many Requests',
        'error_description': (
            'You have submitted too many requests in a short period.'
        ),
        'context_title': 'Rate Limit Notice',
        'context_message': (
            'To protect system stability and maintain fair resource availability across all departments, '
            'dynamic requests are temporarily limited. Please wait a moment before trying again.'
        ),
        'icon_name': 'clock',
        'icon_tone': 'gold',
        'retry_action': True,
        'retry_label': 'Try Again Later',
        'primary_action_url': '/',
        'primary_action_label': 'Return to Dashboard',
    }
    response = render(request, 'error_generic.html', context, status=429)
    response['Retry-After'] = str(retry_after)
    response['Cache-Control'] = 'no-store'
    return response


def generic_error(request, status_code, title=None, description=None, context_message=None):
    """Dispatcher for other HTTP error codes."""
    defaults = {
        401: {
            'error_title': 'Session Expired',
            'error_description': 'Your authentication session has expired or credentials are required to proceed.',
            'context_title': 'Authentication Required',
            'context_message': 'Please sign in again to resume your accreditation workflow without losing progress.',
            'icon_name': 'lock',
            'icon_tone': 'maroon',
            'primary_action_url': '/login/',
            'primary_action_label': 'Sign In Again',
            'primary_action_icon': 'lock',
            'secondary_action_url': '/',
            'secondary_action_label': 'Return to Dashboard',
            'secondary_action_icon': 'home',
        },
        405: {
            'error_title': 'Method Not Allowed',
            'error_description': 'The requested HTTP method is not supported for this address.',
            'context_title': 'Action Restriction',
            'context_message': 'Please use the interactive buttons and controls provided on the page.',
            'icon_name': 'alert',
            'icon_tone': 'slate',
            'primary_action_url': '/',
            'primary_action_label': 'Return to Dashboard',
            'secondary_action_url': 'javascript:history.back()',
            'secondary_action_label': 'Go Back',
        },
        408: {
            'error_title': 'Request Timeout',
            'error_description': 'The server timed out waiting for the request to complete.',
            'context_title': 'Network Latency',
            'context_message': 'A temporary network interruption occurred while transferring your request. Please try again.',
            'icon_name': 'clock',
            'icon_tone': 'gold',
            'retry_action': True,
            'primary_action_url': '/',
        },
        409: {
            'error_title': 'Workflow Conflict',
            'error_description': 'This record was modified by another workflow participant while your request was processing.',
            'context_title': 'State Conflict',
            'context_message': 'Please refresh the submission page to load the most current stage before making changes.',
            'icon_name': 'layers',
            'icon_tone': 'gold',
            'retry_action': True,
            'retry_label': 'Refresh Page',
            'primary_action_url': '/',
        },
        413: {
            'error_title': 'Upload Size Limit Exceeded',
            'error_description': 'The uploaded file or request body exceeds the maximum permitted size.',
            'context_title': 'Evidence Upload Limit',
            'context_message': 'Please select a smaller file (recommended under 25MB for evidence documents) or compress the document before uploading.',
            'icon_name': 'upload-cloud',
            'icon_tone': 'rose',
            'secondary_action_url': 'javascript:history.back()',
            'secondary_action_label': 'Choose Another File',
            'secondary_action_icon': 'arrow-left',
            'primary_action_url': '/',
            'primary_action_label': 'Return to Dashboard',
        },
        422: {
            'error_title': 'Validation Could Not Be Completed',
            'error_description': 'The submission was well-formed but contains business rules that could not be validated.',
            'context_title': 'Validation Notice',
            'context_message': 'Please review the highlighted form requirements and correct any invalid entries.',
            'icon_name': 'alert',
            'icon_tone': 'rose',
            'secondary_action_url': 'javascript:history.back()',
            'secondary_action_label': 'Go Back',
            'primary_action_url': '/',
        },
        502: {
            'error_title': 'Gateway Connection Error',
            'error_description': 'The gateway server received an invalid response from an upstream service.',
            'context_title': 'Gateway Notice',
            'context_message': 'The proxy or gateway server could not establish a stable connection. Please try again.',
            'icon_name': 'server',
            'icon_tone': 'rose',
            'retry_action': True,
            'primary_action_url': '/',
        },
        503: {
            'error_title': 'Service Temporarily Unavailable',
            'error_description': 'The JMCFI AMS could not reach the required service.',
            'context_title': 'Service Notice',
            'context_message': 'The accreditation service is temporarily unavailable or undergoing scheduled maintenance. Please try again in a few moments.',
            'icon_name': 'server',
            'icon_tone': 'rose',
            'retry_action': True,
            'primary_action_url': '/',
        },
        504: {
            'error_title': 'Gateway Timeout',
            'error_description': 'The gateway timed out waiting for the service to respond.',
            'context_title': 'Service Latency',
            'context_message': 'The accreditation service took too long to complete the requested operation. Please try again.',
            'icon_name': 'clock',
            'icon_tone': 'rose',
            'retry_action': True,
            'primary_action_url': '/',
        },
    }

    item = defaults.get(status_code, {
        'error_title': 'Request Error',
        'error_description': 'The system encountered an error processing your request.',
        'context_title': 'Status Notice',
        'context_message': 'Please return to the dashboard or contact your accreditation administrator.',
        'icon_name': 'alert',
        'icon_tone': 'slate',
        'primary_action_url': '/',
        'primary_action_label': 'Return to Dashboard',
    })

    context = {
        'status_code': status_code,
        'error_title': title or item.get('error_title'),
        'error_description': description or item.get('error_description'),
        'context_title': item.get('context_title'),
        'context_message': context_message or item.get('context_message'),
        'icon_name': item.get('icon_name', 'alert'),
        'icon_tone': item.get('icon_tone', 'maroon'),
        'retry_action': item.get('retry_action', False),
        'retry_label': item.get('retry_label', 'Try Again'),
        'primary_action_url': item.get('primary_action_url'),
        'primary_action_label': item.get('primary_action_label', 'Return to Dashboard'),
        'primary_action_icon': item.get('primary_action_icon', 'home'),
        'secondary_action_url': item.get('secondary_action_url'),
        'secondary_action_label': item.get('secondary_action_label'),
        'secondary_action_icon': item.get('secondary_action_icon', 'arrow-left'),
    }
    return render(request, 'error_generic.html', context, status=status_code)