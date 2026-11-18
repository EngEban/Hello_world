"""Country and phone-number fields for member profiles.

Country codes are ISO 3166-1 alpha-2 (plus ``XK`` for Kosovo, the widely used
user-assigned code that phones, browsers and the frontend library also use).
Names come from the ``phonenumbers`` package's bundled locale data, so the list
stays maintained with the library instead of a hand-written copy.

Phone numbers are validated with ``phonenumbers`` (Google libphonenumber) and
stored in E.164 form, e.g. ``+447911123456``.
"""

from functools import lru_cache

import phonenumbers
from django.core.exceptions import ValidationError
from phonenumbers.geodata.locale import LOCALE_DATA


# ``AN`` (Netherlands Antilles) was withdrawn from ISO 3166-1 in 2010.
_RETIRED_CODES = {'AN'}
_EXTRA_CODES = {'XK': 'Kosovo'}
PHONE_MAX_LENGTH = 16  # "+" and at most 15 digits (ITU-T E.164)


def _english_name(data):
    name = data.get('en', '')
    if name.startswith('*'):  # "*xx" means "same as the xx entry"
        name = data.get(name[1:], '')
    return name


@lru_cache(maxsize=1)
def country_names():
    names = {
        code: _english_name(data) or code
        for code, data in LOCALE_DATA.items()
        if len(code) == 2 and code.isalpha() and code not in _RETIRED_CODES
    }
    names.update(_EXTRA_CODES)
    return dict(sorted(names.items(), key=lambda item: item[1]))


def country_name(code):
    return country_names().get(code or '', '')


def clean_country(value):
    """Return an upper-case country code, '' for blank, or raise ValidationError."""
    if value is None:
        return ''
    if not isinstance(value, str):
        raise ValidationError('Country must be a two-letter country code.')
    code = value.strip().upper()
    if not code:
        return ''
    if code not in country_names():
        raise ValidationError('Choose a country from the list.')
    return code


def clean_phone_number(value, country=''):
    """Return the number in E.164 form, '' for blank, or raise ValidationError.

    International input (``+44 7911 123456``) is accepted on its own; a national
    number (``07911 123456``) is accepted when a country is known.
    """
    if value is None:
        return ''
    if not isinstance(value, str):
        raise ValidationError('Phone number must be text.')
    raw = value.strip()
    if not raw:
        return ''
    if len(raw) > 40:
        raise ValidationError('Phone number is too long.')
    region = country if country and not raw.startswith('+') else None
    try:
        number = phonenumbers.parse(raw, region)
    except phonenumbers.NumberParseException:
        raise ValidationError('Enter a valid phone number including the country code, for example +44 7911 123456.')
    if not phonenumbers.is_valid_number(number):
        raise ValidationError('This phone number is not valid for the selected country code.')
    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)
