from django.core.management.base import BaseCommand

from dashboard.outbox import process_outbox


class Command(BaseCommand):
    help = 'Send queued newsletter emails (run every few minutes by a cron service).'

    def add_arguments(self, parser):
        parser.add_argument('--batch-size', type=int, default=None, help='Max recipients per campaign per run.')

    def handle(self, *args, **options):
        totals = process_outbox(options['batch_size'])
        self.stdout.write(
            f"Outbox: {totals['campaigns']} campaign(s), {totals['sent']} sent, "
            f"{totals['failed']} failed, {totals['retry']} to retry."
        )
