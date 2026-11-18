from django.core.management.base import BaseCommand

from accounts.entitlements import ensure_default_entitlements


class Command(BaseCommand):
    help = 'Create missing default roles, features, plans and usage limits (idempotent).'

    def handle(self, *args, **options):
        ensure_default_entitlements()
        self.stdout.write(self.style.SUCCESS('Reference data is up to date.'))
