"""Email backend that sends through Brevo's HTTPS API instead of SMTP.

Railway blocks outbound SMTP (ports 25/465/587) on its Trial and Hobby plans, so
the SMTP relay silently times out there. HTTPS (port 443) is always allowed.
Configure with BREVO_API_KEY (Brevo → SMTP & API → API Keys, starts "xkeysib-").
The sender is the message's from_email (DJANGO_DEFAULT_FROM_EMAIL by default),
which must be an address on a domain authenticated in Brevo.
"""
import logging
from email.utils import getaddresses, parseaddr

import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

BREVO_SEND_URL = 'https://api.brevo.com/v3/smtp/email'


def _contact(value):
    name, address = parseaddr(value or '')
    contact = {'email': address}
    if name:
        contact['name'] = name
    return contact


def _contacts(values):
    return [{'email': address, **({'name': name} if name else {})} for name, address in getaddresses(values or []) if address]


class BrevoApiEmailBackend(BaseEmailBackend):
    def __init__(self, api_key=None, timeout=None, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently)
        self.api_key = api_key or getattr(settings, 'BREVO_API_KEY', '')
        self.timeout = timeout or getattr(settings, 'EMAIL_TIMEOUT', None) or 15

    def _payload(self, message):
        html = None
        for content, mimetype in getattr(message, 'alternatives', None) or []:
            if mimetype == 'text/html':
                html = content
        if getattr(message, 'content_subtype', 'plain') == 'html':
            html, text = message.body, None
        else:
            text = message.body
        payload = {
            'sender': _contact(message.from_email or settings.DEFAULT_FROM_EMAIL),
            'to': _contacts(message.to),
            'subject': message.subject,
        }
        if message.cc:
            payload['cc'] = _contacts(message.cc)
        if message.bcc:
            payload['bcc'] = _contacts(message.bcc)
        if message.reply_to:
            payload['replyTo'] = _contact(message.reply_to[0])
        if html:
            payload['htmlContent'] = html
        if text:
            payload['textContent'] = text
        if not html and not text:
            payload['textContent'] = ' '
        headers = {key: value for key, value in (message.extra_headers or {}).items() if key.lower() not in {'from', 'to', 'cc', 'bcc', 'subject', 'reply-to'}}
        if headers:
            payload['headers'] = headers
        return payload

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        if not self.api_key:
            if not self.fail_silently:
                raise RuntimeError('BREVO_API_KEY is not set.')
            return 0
        sent = 0
        session = requests.Session()
        for message in email_messages:
            if not message.recipients():
                continue
            try:
                response = session.post(
                    BREVO_SEND_URL,
                    json=self._payload(message),
                    headers={'api-key': self.api_key, 'accept': 'application/json', 'content-type': 'application/json'},
                    timeout=self.timeout,
                )
                if response.status_code >= 300:
                    # Brevo explains the problem (e.g. unauthorised key, unverified sender) in the body.
                    raise RuntimeError(f'Brevo API returned {response.status_code}: {response.text[:300]}')
                sent += 1
            except Exception:
                if not self.fail_silently:
                    raise
                logger.exception('Brevo API email could not be sent.')
        return sent
