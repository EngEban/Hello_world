from django.conf import settings


class SecurityHeadersMiddleware:
    """Apply deploy-time browser hardening headers without adding a dependency."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault('X-Content-Type-Options', 'nosniff')
        response.setdefault('Referrer-Policy', getattr(settings, 'SECURE_REFERRER_POLICY', 'same-origin'))
        response.setdefault('Cross-Origin-Opener-Policy', 'same-origin')
        response.setdefault('Permissions-Policy', getattr(settings, 'RESREF_PERMISSIONS_POLICY', ''))
        if getattr(settings, 'RESREF_CSP_ENABLED', False):
            header = 'Content-Security-Policy-Report-Only' if getattr(settings, 'RESREF_CSP_REPORT_ONLY', False) else 'Content-Security-Policy'
            response.setdefault(header, getattr(settings, 'RESREF_CONTENT_SECURITY_POLICY', ''))
        return response
