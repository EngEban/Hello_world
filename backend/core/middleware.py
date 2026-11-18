"""Platform-level request guards."""

from django.conf import settings
from django.http import HttpResponsePermanentRedirect

from core.errors import api_error_response


class RequestSizeLimitMiddleware:
    """Reject oversized request bodies before Django reads them.

    ``DATA_UPLOAD_MAX_MEMORY_SIZE`` does not cover file uploads, and gunicorn
    has no body-size limit, so without this a single anonymous multipart POST
    (for example to the public CV upload) could stream gigabytes into the
    container's temporary disk before the per-field validation runs. The cap
    is above the largest legitimate upload (the 20 MB analyzer dataset).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        limit = getattr(settings, 'RESREF_MAX_REQUEST_BYTES', 0)
        if limit:
            try:
                length = int(request.META.get('CONTENT_LENGTH') or 0)
            except (TypeError, ValueError):
                length = 0
            if length > limit:
                megabytes = max(limit // (1024 * 1024), 1)
                return api_error_response(413, f'The upload is too large. The limit is {megabytes} MB.', 'request_too_large')
        return self.get_response(request)


class WwwRedirectMiddleware:
    """Send www.<PUBLIC_HOSTNAME> to the main address.

    Both names reach the app, so without this search engines see every page
    twice. Only page loads move; anything else (forms, API calls) is left alone.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        public_host = getattr(settings, 'PUBLIC_HOSTNAME', '')
        if public_host and request.method in ('GET', 'HEAD') and request.get_host().split(':')[0].lower() == f'www.{public_host}':
            return HttpResponsePermanentRedirect(f'{request.scheme}://{public_host}{request.get_full_path()}')
        return self.get_response(request)
