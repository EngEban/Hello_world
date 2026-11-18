"""Sample size studio API: design catalogue, live calculation and Word export.

Calculations are free to explore (they update live as the researcher types); the usage allowance is
charged by the page through ``/api/usage/sample_size_calculator/consume/`` when a result is copied,
exported or saved.
"""
import json

from django.http import HttpResponse
from django.views.decorators.http import require_GET, require_POST

from accounts.security import rate_limit
from usage import services as usage

from .views import _bad, _json_response

FEATURE_CODE = 'sample_size_calculator'


def _require_access(request):
    denied = usage.access_denial(usage.subject_for(request), FEATURE_CODE)
    if denied is not None:
        return _bad(denied.message, denied.status, denied.code)
    return None


def _payload(request):
    try:
        data = json.loads(request.body.decode('utf-8') or '{}')
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


@require_GET
def designs(request):
    blocked = _require_access(request)
    if blocked:
        return blocked
    from .engine.sample_size import catalog
    return _json_response(catalog())


@require_POST
def calculate(request):
    blocked = _require_access(request)
    if blocked:
        return blocked
    if not rate_limit(request, 'sample-size-calculate', limit=1200, window=3600):
        return _bad('Too many calculations. Please wait a moment.', 429)
    payload = _payload(request)
    if payload is None or not isinstance(payload.get('inputs', {}), dict):
        return _bad('Invalid request payload.')
    from .engine.sample_size import PlanningError, calculate as run
    mode = str(payload.get('mode', 'n'))
    if mode not in {'n', 'power', 'mde', 'precision'}:
        return _bad('Unknown calculation mode.')
    try:
        result = run(str(payload.get('design', '')), mode, payload.get('inputs', {}))
    except PlanningError as exc:
        return _bad(str(exc), 422, 'planning')
    except (ValueError, ZeroDivisionError, OverflowError):
        return _bad('These assumptions cannot be calculated. Check that the values are realistic.', 422, 'planning')
    return _json_response({'success': True, **result})


@require_POST
def export_docx(request):
    blocked = _require_access(request)
    if blocked:
        return blocked
    if not rate_limit(request, 'sample-size-export', limit=60, window=3600):
        return _bad('Too many exports. Please wait before trying again.', 429)
    if len(request.body) > 512 * 1024:
        return _bad('The report is too large to export.', 413)
    payload = _payload(request)
    if payload is None or not isinstance(payload.get('report'), dict):
        return _bad('Invalid report payload.')
    from .engine.report_docx import build
    response = HttpResponse(build(payload['report']), content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    response['Content-Disposition'] = 'attachment; filename="sample-size.docx"'
    return response
