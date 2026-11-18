from django.db import migrations, models


def clear_primary_author_only_contributors(apps, schema_editor):
    Post = apps.get_model('blog', 'Post')
    through = Post.authors.through
    for post in Post.objects.exclude(author_id__isnull=True).only('id', 'author_id'):
        author_ids = list(through.objects.filter(post_id=post.id).values_list('author_id', flat=True))
        if author_ids and set(author_ids) == {post.author_id}:
            through.objects.filter(post_id=post.id, author_id=post.author_id).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0004_category_database_controls_post_authors_pdf'),
    ]

    operations = [
        migrations.AddField(
            model_name='author',
            name='role',
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.RunPython(clear_primary_author_only_contributors, migrations.RunPython.noop),
    ]
