from django.core.management.base import BaseCommand

from research_analyzer.session_store import cleanup_expired, cleanup_orphans


class Command(BaseCommand):
    help = 'Delete expired Research Analyzer sessions and their dataset files.'

    def handle(self, *args, **options):
        sessions = cleanup_expired()
        orphans = cleanup_orphans()
        self.stdout.write(f'Removed {sessions} expired session(s) and {orphans} orphaned file(s).')
