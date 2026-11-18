"""JSON errors for every /api/ URL (T-14; moved from resref/api_errors.py in T-20).

The React app always expects JSON from /api/. Without this, a missing route,
a wrong method, a CSRF failure or an unhandled exception returned Django's
HTML page, which the client could only show as "API request failed (500)".
"""

import json
import logging

from django.core.exceptions import BadRequest, PermissionDenied, SuspiciousOperation
from django.http import Http404, JsonResponse
from django.views.csrf import csrf_failure as html_csrf_failure

logger = logging.getLogger('resref.api')

DEFAULT_MESSAGES = {
    400: 'The request could not be understood.',
    401: 'Please sign in to continue.',
    403: 'You do not have permission to do that.',
    404: 'Not found.',
    405: 'This method is not allowed here.',
    413: 'The request is too large.',
    500: 'Something went wrong on our side. Please try again.',
}


def is_api_request(request):
    return request.path.startswith('/api/')


def api_error_response(status, message=None, code=None):
    payload = {'success': False, 'error': message or DEFAULT_MESSAGES.get(status, 'Request failed.')}
    if code:
        payload['code'] = code
    return JsonResponse(payload, status=status)


class ApiErrorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not is_api_request(request) or response.status_code < 400:
            return response
        content_type = response.get('Content-Type', '')
        if content_type.startswith('application/json') or getattr(response, 'streaming', False):
            return response
        # e.g. require_POST's 405 or a plain HttpResponse error: re-wrap as JSON.
        converted = api_error_response(response.status_code)
        if response.status_code == 405 and response.has_header('Allow'):
            converted['Allow'] = response['Allow']
        return converted

    def process_exception(self, request, exception):
        if not is_api_request(request):
            return None
        if isinstance(exception, Http404):
            return api_error_response(404)
        if isinstance(exception, PermissionDenied):
            return api_error_response(403)
        if isinstance(exception, BadRequest):
            return api_error_response(400, str(exception) or None)
        if isinstance(exception, SuspiciousOperation):
            logger.warning('Suspicious API request to %s: %s', request.path, exception)
            return api_error_response(400)
        if isinstance(exception, (json.JSONDecodeError, UnicodeDecodeError)):
            return api_error_response(400, 'Invalid request payload.')
        logger.exception('Unhandled error on %s %s', request.method, request.path)
        return api_error_response(500)


def csrf_failure(request, reason=''):
    if is_api_request(request):
        return api_error_response(403, 'Security check failed. Refresh the page and try again.', 'csrf_failed')
    return html_csrf_failure(request, reason=reason)


def handler404(request, exception=None):
    if is_api_request(request):
        return api_error_response(404)
    from django.views.defaults import page_not_found
    return page_not_found(request, exception)


def handler500(request):
    if is_api_request(request):
        return api_error_response(500)
    from django.views.defaults import server_error
    return server_error(request)


def error_response(message, status=400):
    return JsonResponse({'success': False, 'error': message}, status=status)
