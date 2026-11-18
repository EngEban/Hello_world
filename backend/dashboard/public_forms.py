"""Public intake endpoints: team applications and service requests (T-13).

Both are anonymous, rate limited per IP and per email, validated server side,
and saved straight into the dashboard models (previously they were squeezed
into a contact message). CVs are checked by size, extension and file
signature, stored under uploads/jobapplication/ (never served publicly) and
downloaded only through the authenticated dashboard endpoint.
"""

import io
import zipfile

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator, validate_email
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from accounts.security import rate_limit
from blog.api_views import api_error, clean_text, validate_optional_phone_number

from .models import JobApplication, ServiceDefinition, ServiceRequest

CV_MAX_BYTES = 5 * 1024 * 1024
TEAM_BY_LABEL = {label.lower(): code for code, label in JobApplication.TEAMS}


def _payload(request):
    if request.content_type and request.content_type.startswith('multipart/form-data'):
        return request.POST
    import json
    try:
        data = json.loads(request.body.decode('utf-8') or '{}')
    except (UnicodeDecodeError, ValueError):
        raise ValidationError('Invalid request payload.')
    if not isinstance(data, dict):
        raise ValidationError('Invalid request payload.')
    return data


def _team_code(value):
    value = (value or '').strip()
    if value in dict(JobApplication.TEAMS):
        return value
    return TEAM_BY_LABEL.get(value.lower(), 'other')


def _validate_cv(upload):
    if upload is None:
        return None
    name = (upload.name or '').lower()
    extension = name.rsplit('.', 1)[-1] if '.' in name else ''
    if extension not in {'pdf', 'docx'}:
        raise ValidationError('CV must be a PDF or Word (.docx) file.')
    if upload.size > CV_MAX_BYTES:
        raise ValidationError('CV must be 5 MB or smaller.')
    head = upload.read(8)
    upload.seek(0)
    if extension == 'pdf' and not head.startswith(b'%PDF-'):
        raise ValidationError('The CV file is not a valid PDF.')
    if extension == 'docx':
        content = upload.read()
        upload.seek(0)
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                if 'word/document.xml' not in archive.namelist():
                    raise ValidationError('The CV file is not a valid Word document.')
        except zipfile.BadZipFile as exc:
            raise ValidationError('The CV file is not a valid Word document.') from exc
    return upload


def _limited(request, scope, email):
    return not (
        rate_limit(request, f'{scope}-ip', limit=10, window=3600)
        and rate_limit(request, f'{scope}-email', email, limit=3, window=3600, include_ip=False)
    )


@require_POST
def submit_application_api(request):
    try:
        data = _payload(request)
        full_name = clean_text(data, 'full_name', 200) or clean_text(data, 'name', 200, required=True)
        email = clean_text(data, 'email', 254, required=True).lower()
        validate_email(email)
        whatsapp = clean_text(data, 'whatsapp', 50)
        validate_optional_phone_number(whatsapp)
        team = _team_code(clean_text(data, 'team', 100) or clean_text(data, 'specialization', 100))
        experience = clean_text(data, 'experience', 5000)
        motivation = clean_text(data, 'motivation', 5000) or clean_text(data, 'message', 5000, required=True)
        portfolio = clean_text(data, 'portfolio', 500)
        if portfolio:
            URLValidator(schemes=['http', 'https'])(portfolio)
        cv = _validate_cv(request.FILES.get('cv'))
    except ValidationError as exc:
        return api_error(' '.join(exc.messages) if exc.messages else 'Please check the form and try again.')
    if _limited(request, 'application', email):
        return api_error('Too many applications. Please try again later.', 429)
    with transaction.atomic():
        application = JobApplication(
            full_name=full_name, email=email, whatsapp=whatsapp, team=team,
            experience=experience, motivation=motivation, portfolio=portfolio,
        )
        if cv is not None:
            application.cv_file.save(cv.name, cv, save=False)
        application.save()
    return JsonResponse({'success': True, 'message': 'Your team application has been received.', 'id': application.pk}, status=201)


@require_POST
def submit_service_request_api(request):
    try:
        data = _payload(request)
        name = clean_text(data, 'name', 200, required=True)
        email = clean_text(data, 'email', 254, required=True).lower()
        validate_email(email)
        whatsapp = clean_text(data, 'whatsapp', 50)
        validate_optional_phone_number(whatsapp)
        organization = clean_text(data, 'organization', 250)
        request_type = clean_text(data, 'request_type', 120) or 'Service request'
        topic = clean_text(data, 'specialization', 200)
        message = clean_text(data, 'message', 5000, required=True)
        service_slug = clean_text(data, 'service', 260)
    except ValidationError as exc:
        return api_error(' '.join(exc.messages) if exc.messages else 'Please check the form and try again.')
    if _limited(request, 'service-request', email):
        return api_error('Too many requests. Please try again later.', 429)
    service = ServiceDefinition.objects.filter(slug=service_slug, status='active').first() if service_slug else None
    subject = f'{request_type}: {topic}' if topic else request_type
    details = message if not whatsapp else f'{message}\n\nWhatsApp: {whatsapp}'
    item = ServiceRequest.objects.create(
        service=service,
        requester_name=name,
        requester_email=email,
        organization=organization,
        subject=subject[:300],
        message=details,
    )
    return JsonResponse({'success': True, 'message': 'Your request has been received.', 'id': item.pk}, status=201)

