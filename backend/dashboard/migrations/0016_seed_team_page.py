"""Start the Team page unpublished, with the three leadership sections ready to fill in."""

from django.db import migrations

SECTIONS = [
    ('Founder & Managing Director', 'founder'),
    ('Board Members', 'leadership'),
    ('Department Directors', 'directors'),
]


def seed(apps, schema_editor):
    apps.get_model('dashboard', 'TeamPageSettings').objects.get_or_create(pk=1)
    section = apps.get_model('dashboard', 'TeamPageSection')
    if not section.objects.exists():
        for position, (name, level) in enumerate(SECTIONS, start=1):
            section.objects.create(name=name, level=level, sort_order=position)


class Migration(migrations.Migration):
    dependencies = [('dashboard', '0015_team_page')]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
