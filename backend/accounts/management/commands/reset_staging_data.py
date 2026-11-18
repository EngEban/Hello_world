"""Clear application data from a PostgreSQL staging database without resetting schema metadata."""

from django.apps import apps
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder


class Command(BaseCommand):
    help = (
        "Deletes all application data from PostgreSQL staging while preserving "
        "migrations, content types, and permissions."
    )

    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            raise CommandError("reset_staging_data only supports PostgreSQL staging databases.")

        preserved_tables = {
            MigrationRecorder.Migration._meta.db_table,
            ContentType._meta.db_table,
            Permission._meta.db_table,
        }
        model_tables = {
            model._meta.db_table
            for model in apps.get_models(include_auto_created=True)
            if model._meta.managed
        }
        existing_tables = set(connection.introspection.table_names())
        tables_to_truncate = sorted((model_tables & existing_tables) - preserved_tables)

        if not tables_to_truncate:
            self.stdout.write("No application tables were found to clear.")
            return

        quoted_tables = ", ".join(connection.ops.quote_name(table) for table in tables_to_truncate)
        with connection.cursor() as cursor:
            cursor.execute(f"TRUNCATE TABLE {quoted_tables} RESTART IDENTITY CASCADE")

        self.stdout.write(
            self.style.SUCCESS(
                f"Cleared {len(tables_to_truncate)} application tables; schema metadata was preserved."
            )
        )
