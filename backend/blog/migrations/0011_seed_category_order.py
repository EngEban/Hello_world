from django.db import migrations

MAIN_CATEGORY_SLUG = 'mastering-research'


def seed_order(apps, schema_editor):
    """Give every category its own position, keeping today's order, with the main category first."""
    Category = apps.get_model('blog', 'Category')
    siblings = {}
    for category in Category.objects.order_by('database_order', 'name'):
        siblings.setdefault(category.parent_id, []).append(category)
    changed = []
    for group in siblings.values():
        group.sort(key=lambda category: category.slug != MAIN_CATEGORY_SLUG)
        for position, category in enumerate(group, start=1):
            category.database_order = position
            changed.append(category)
    Category.objects.bulk_update(changed, ['database_order'])


class Migration(migrations.Migration):
    dependencies = [('blog', '0010_mediaasset_optimized_file')]
    operations = [migrations.RunPython(seed_order, migrations.RunPython.noop)]
