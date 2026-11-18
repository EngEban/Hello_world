"""Import (or re-import) a WordPress site safely.

    python manage.py import_wordpress export.xml --dry-run
    python manage.py import_wordpress resref.sql --uploads-dir ./uploads --dry-run --report report.json
    python manage.py import_wordpress resref.sql --uploads-dir ./uploads          # real run, asks to confirm

Never deletes data. See docs/launch/wordpress-migration.md for the runbook.
"""
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_date, parse_datetime
from django.utils import timezone

from blog.wordpress.importer import DEFAULT_ENTITIES, ENTITY_ORDER, Report, WordPressImporter
from blog.wordpress.media import MediaSourceError
from blog.wordpress.sources import read_source


def parse_moment(value):
    moment = parse_datetime(value)
    if moment is None:
        day = parse_date(value)
        if day is None:
            raise CommandError(f'Not a date: {value!r} (use YYYY-MM-DD or YYYY-MM-DDTHH:MM)')
        moment = datetime(day.year, day.month, day.day)
    return timezone.make_aware(moment) if timezone.is_naive(moment) else moment


class Command(BaseCommand):
    help = 'Import a WordPress WXR export or SQL dump. Repeatable, never deletes, --dry-run shows a full report first.'

    def add_arguments(self, parser):
        parser.add_argument('source', help='WordPress export: WXR .xml file or MySQL .sql dump')
        parser.add_argument('--format', choices=['auto', 'wxr', 'sql'], default='auto')
        parser.add_argument('--table-prefix', default=None, help='SQL dumps: table prefix (auto-detected, usually wp_)')
        parser.add_argument('--dry-run', action='store_true', help='Change nothing; print what would happen')
        parser.add_argument('--only', default='', help=f'Comma-separated subset of: {", ".join(ENTITY_ORDER)} (default: {", ".join(DEFAULT_ENTITIES)}; users must be asked for)')
        parser.add_argument('--overwrite', action='store_true', help='Take the WordPress value even where the field was edited in the new site')
        parser.add_argument('--uploads-dir', default=None, help='Local copy of wp-content/uploads to copy files from')
        parser.add_argument('--media-base-url', default=None, help='Download missing files from here, e.g. https://old.resref.com/wp-content/uploads/')
        parser.add_argument('--optimize-images', action='store_true', help='Also create the WebP delivery copy for imported images')
        parser.add_argument('--import-password-hashes', action='store_true', help='Users: keep WordPress password hashes (needs the WordPress hasher in PASSWORD_HASHERS)')
        parser.add_argument('--published-only', action='store_true', help='Only import published posts and pages')
        parser.add_argument('--skip-trash', action='store_true', help='Do not import trashed posts and pages')
        parser.add_argument('--trust-unedited-before', default=None, help='Rows from the earlier import not updated since this date count as unedited')
        parser.add_argument('--no-assume-unedited', action='store_true', help='Do not treat rows untouched since the earlier import as unedited')
        parser.add_argument('--report', default=None, help='Also write the full report as JSON to this file')
        parser.add_argument('--no-input', '--noinput', action='store_false', dest='interactive', help='Do not ask for confirmation')

    def handle(self, *args, **options):
        source = Path(options['source'])
        if not source.is_file():
            raise CommandError(f'File not found: {source}')
        only = [name.strip() for name in options['only'].split(',') if name.strip()] or list(DEFAULT_ENTITIES)
        unknown = sorted(set(only) - set(ENTITY_ORDER))
        if unknown:
            raise CommandError(f'Unknown entity: {", ".join(unknown)}. Choose from {", ".join(ENTITY_ORDER)}.')
        trust = parse_moment(options['trust_unedited_before']) if options['trust_unedited_before'] else None

        self.stdout.write(f'Reading {source} ...')
        try:
            data = read_source(source, options['format'], options['table_prefix'])
        except Exception as exc:
            raise CommandError(f'Could not read the export: {exc}') from exc
        self.stdout.write(
            f'Found {len(data.items)} posts/pages, {len(data.attachments)} media, {len(data.categories)} categories, '
            f'{len(data.tags)} tags, {len(data.authors)} authors, {len(data.users)} user accounts, {len(data.redirects)} redirect rules ({data.source_format}).'
        )
        dry_run = options['dry_run']
        if not dry_run and options['interactive']:
            self.stdout.write(self.style.WARNING(
                'This writes to the database configured in DATABASE_URL. Take a pg_dump backup first and run --dry-run before.'
            ))
            if input('Type "import" to continue: ').strip() != 'import':
                raise CommandError('Cancelled; nothing was changed.')
        try:
            importer = WordPressImporter(
                data, dry_run=dry_run, only=only, overwrite=options['overwrite'], uploads_dir=options['uploads_dir'],
                media_base_url=options['media_base_url'], optimize_images=options['optimize_images'],
                import_password_hashes=options['import_password_hashes'], published_only=options['published_only'],
                skip_trash=options['skip_trash'], trust_unedited_before=trust, assume_unedited=not options['no_assume_unedited'],
                log=lambda message: self.stdout.write(message) if options['verbosity'] > 1 else None,
            )
        except MediaSourceError as exc:
            raise CommandError(str(exc)) from exc
        try:
            report = importer.run()
        except Exception as exc:
            self.print_report(importer.report, dry_run, options)
            raise CommandError(f'Import stopped; the failing batch was rolled back: {exc}') from exc
        self.print_report(report, dry_run, options)

    def print_report(self, report: Report, dry_run, options):
        out = self.stdout
        out.write('')
        out.write(self.style.MIGRATE_HEADING('DRY RUN - nothing was saved, no files were copied' if dry_run else 'WordPress import finished'))
        columns = Report.OUTCOMES
        out.write(f'{"entity":<14}' + ''.join(f'{name:>10}' for name in columns))
        for entity, counter in report.counts.items():
            out.write(f'{entity:<14}' + ''.join(f'{counter.get(name, 0):>10}' for name in columns))
        for entity, counter in report.extra.items():
            for label, count in counter.items():
                out.write(f'  {entity}: {label}: {count}')
        for note in report.notes:
            out.write(self.style.WARNING(f'Note: {note}'))
        verbose = options['verbosity'] > 1
        shown = [row for row in report.details if verbose or row['outcome'] in {'conflict', 'error'}]
        if shown:
            out.write('')
            for row in shown[:500]:
                fields = f" [{', '.join(row['fields'])}]" if row['fields'] else ''
                out.write(f"{row['outcome'].upper():<9} {row['entity']} {row['key']}{fields} {row['message']}")
            if len(shown) > 500:
                out.write(f'... {len(shown) - 500} more lines; use --report to save everything.')
        if options.get('report'):
            Path(options['report']).write_text(report.dumps(), encoding='utf-8')
            out.write(f'Full report written to {options["report"]}')
