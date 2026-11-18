from django.db import migrations

from blog.legacy_credits import restore_article_credits_v1


def restore_explicit_credits(apps, schema_editor):
    Post = apps.get_model('blog', 'Post')
    Author = apps.get_model('blog', 'Author')
    PostContributor = apps.get_model('blog', 'PostContributor')
    using = schema_editor.connection.alias
    # Never use uploaders, deleted content or rewrite source HTML.
    posts = Post.objects.using(using).filter(post_type='post').exclude(status='trash')
    for post in posts.iterator():
        restore_article_credits_v1(post, Author, PostContributor, using=using)


class Migration(migrations.Migration):
    dependencies = [('blog', '0008_category_description_hero_image')]
    # Retain recovered editorial records on rollback; deletion is unsafe.
    operations = [migrations.RunPython(restore_explicit_credits, migrations.RunPython.noop)]
