"""Create a one-time staging administrator from explicitly supplied env vars."""

import os

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from accounts.identity import find_user_by_identifier, normalize_email


class Command(BaseCommand):
    help = (
        'Creates a staging superuser when all RESREF_STAGING_ADMIN_* variables '
        'are supplied in a non-production environment. Existing users require '
        'RESREF_STAGING_ADMIN_ALLOW_PROMOTION=true before they can be promoted.'
    )

    def handle(self, *args, **options):
        configured_names = [
            name for name in settings.STAGING_ADMIN_ENVIRONMENT_VARIABLES if name in os.environ
        ]
        if settings.IS_PRODUCTION:
            if configured_names:
                raise CommandError(
                    'Refusing staging administrator bootstrap in production; remove: '
                    + ', '.join(configured_names)
                )
            self.stdout.write('Production environment: staging administrator bootstrap is disabled.')
            return

        username = os.getenv('RESREF_STAGING_ADMIN_USERNAME', '').strip()
        email = normalize_email(os.getenv('RESREF_STAGING_ADMIN_EMAIL', ''))
        password = os.getenv('RESREF_STAGING_ADMIN_PASSWORD', '')
        reset_password = os.getenv('RESREF_STAGING_ADMIN_RESET_PASSWORD', '').strip().lower() in {
            '1', 'true', 'yes', 'on',
        }
        allow_promotion = os.getenv('RESREF_STAGING_ADMIN_ALLOW_PROMOTION', '').strip().lower() in {
            '1', 'true', 'yes', 'on',
        }
        supplied = [bool(username), bool(email), bool(password)]

        if not any(supplied):
            self.stdout.write('Staging administrator is not configured; skipping bootstrap.')
            return
        if not all(supplied):
            raise CommandError(
                'Set RESREF_STAGING_ADMIN_USERNAME, RESREF_STAGING_ADMIN_EMAIL, '
                'and RESREF_STAGING_ADMIN_PASSWORD together, or set none of them.'
            )

        user_model = get_user_model()
        user = user_model.objects.filter(username__iexact=username).first()
        email_user = find_user_by_identifier(email)

        if reset_password and user and email_user and user.pk != email_user.pk:
            raise CommandError('The requested username and email belong to different existing accounts.')
        if email_user and not user:
            raise CommandError('The requested email already belongs to a different username.')

        if user:
            if user.is_superuser:
                self.stdout.write(
                    self.style.WARNING(
                        f'Staging administrator "{user.username}" already exists as a superuser; no changes made.'
                    )
                )
                return
            if not allow_promotion:
                self.stderr.write(
                    self.style.WARNING(
                        f'Existing account "{user.username}" was not promoted; '
                        'set RESREF_STAGING_ADMIN_ALLOW_PROMOTION=true for an explicit promotion.'
                    )
                )
                return
            try:
                validate_password(password, user)
            except ValidationError as error:
                raise CommandError(' '.join(error.messages)) from error

            if reset_password and user.email.lower() != email:
                user.email = email
            if reset_password:
                user.set_password(password)
            user.is_staff = True
            user.is_superuser = True
            user.save()
            self.stdout.write(self.style.SUCCESS(f'Promoted existing staging administrator "{user.username}".'))
            return

        candidate = user_model(username=username, email=email)
        try:
            validate_password(password, candidate)
        except ValidationError as error:
            raise CommandError(' '.join(error.messages)) from error

        user_model.objects.create_superuser(username=username, email=email, password=password)
        self.stdout.write(self.style.SUCCESS(f'Created staging administrator "{username}".'))
