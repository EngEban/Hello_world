"""Log formatting and redaction for the platform logs (stdout on Railway)."""

import json
import logging
import re
from datetime import datetime, timezone

# key=value / "key": "value" pairs whose value must never reach a log line.
_SECRET_PATTERN = re.compile(
    r'(?i)(["\']?(?:password|passwd|secret|token|api[_-]?key|authorization|cookie|sessionid|csrftoken)["\']?\s*[:=]\s*)'
    r'("[^"]*"|\'[^\']*\'|[^\s,&;]+)'
)
# Query-string tokens in URLs (password reset, e-mail confirmation, ...).
_URL_TOKEN_PATTERN = re.compile(r'(?i)([?&](?:token|key|code|signature|uid)=)[^&\s"]+')


def redact(text):
    text = _SECRET_PATTERN.sub(r'\1[REDACTED]', text)
    return _URL_TOKEN_PATTERN.sub(r'\1[REDACTED]', text)


class RedactSecretsFilter(logging.Filter):
    """Masks passwords, tokens and keys in the rendered log message."""

    def filter(self, record):
        try:
            message = record.getMessage()
        except Exception:  # never let logging break a request
            return True
        cleaned = redact(message)
        if cleaned != message:
            record.msg = cleaned
            record.args = ()
        return True


class JsonFormatter(logging.Formatter):
    """One JSON object per line, easy to search in Railway's log explorer."""

    def format(self, record):
        payload = {
            'time': datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }
        status_code = getattr(record, 'status_code', None)
        if status_code is not None:
            payload['status_code'] = status_code
        if record.exc_info:
            payload['exception'] = redact(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False, default=str)
