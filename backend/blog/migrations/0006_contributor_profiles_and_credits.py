from django.db import migrations, models
import django.db.models.deletion
from django.utils.text import slugify
from django.utils import timezone


def backfill_author_slugs_and_credits(apps, schema_editor):
    Author = apps.get_model('blog', 'Author')
    Post = apps.get_model('blog', 'Post')
    PostContributor = apps.get_model('blog', 'PostContributor')
    # Existing WordPress-era authors predate these audit fields. Populate both
    # before this migration tightens them to NOT NULL on PostgreSQL.
    now = timezone.now()
    Author.objects.filter(created_at__isnull=True).update(created_at=now)
    Author.objects.filter(updated_at__isnull=True).update(updated_at=now)
    used = set()
    for author in Author.objects.order_by('id'):
        base = slugify(author.display_name) or slugify(author.login) or f'contributor-{author.id}'
        slug = base[:220]
        suffix = 2
        while slug in used:
            ending = f'-{suffix}'
            slug = f'{base[:220-len(ending)]}{ending}'
            suffix += 1
        author.slug = slug
        author.save(update_fields=['slug'])
        used.add(slug)
    # M2M records were already explicit public content credits.  A legacy
    # primary byline can mean WordPress uploader metadata, so leave it intact
    # rather than guessing that it is an authorship credit.
    through = Post.authors.through
    for post_id, author_id in through.objects.values_list('post_id', 'author_id'):
        PostContributor.objects.get_or_create(post_id=post_id, contributor_id=author_id, role='author')


class Migration(migrations.Migration):
    dependencies = [('blog', '0005_author_role_clear_legacy_contributors')]
    operations = [
        migrations.AddField(model_name='author', name='country', field=models.CharField(blank=True, max_length=120)),
        migrations.AddField(model_name='author', name='created_at', field=models.DateTimeField(auto_now_add=True, null=True)),
        migrations.AddField(model_name='author', name='credentials', field=models.CharField(blank=True, max_length=160)),
        migrations.AddField(model_name='author', name='display_order', field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name='author', name='google_scholar', field=models.URLField(blank=True, max_length=1000)),
        migrations.AddField(model_name='author', name='institution', field=models.CharField(blank=True, max_length=250)),
        migrations.AddField(model_name='author', name='is_active', field=models.BooleanField(default=True)),
        migrations.AddField(model_name='author', name='orcid', field=models.URLField(blank=True, max_length=1000)),
        migrations.AddField(model_name='author', name='position', field=models.CharField(blank=True, max_length=200)),
        migrations.AddField(model_name='author', name='prefix', field=models.CharField(blank=True, max_length=40)),
        migrations.AddField(model_name='author', name='profile_media', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='contributor_profiles', to='blog.mediaasset')),
        migrations.AddField(model_name='author', name='researchgate', field=models.URLField(blank=True, max_length=1000)),
        migrations.AddField(model_name='author', name='seo_description', field=models.TextField(blank=True)),
        migrations.AddField(model_name='author', name='seo_title', field=models.CharField(blank=True, max_length=500)),
        migrations.AddField(model_name='author', name='short_bio', field=models.TextField(blank=True)),
        migrations.AddField(model_name='author', name='slug', field=models.SlugField(blank=True, max_length=220, null=True, unique=True)),
        migrations.AddField(model_name='author', name='specialty', field=models.CharField(blank=True, max_length=200)),
        migrations.AddField(model_name='author', name='updated_at', field=models.DateTimeField(auto_now=True, null=True)),
        migrations.CreateModel(name='PostContributor', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('role', models.CharField(choices=[('author', 'Author'), ('co_author', 'Co-author'), ('editor', 'Editor'), ('reviewer', 'Reviewer'), ('translator', 'Translator'), ('formatter', 'Formatter')], default='author', max_length=32)),
            ('display_order', models.PositiveIntegerField(default=0)),
            ('contribution_note', models.TextField(blank=True)),
            ('contributor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='contributions', to='blog.author')),
            ('post', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='contributor_assignments', to='blog.post')),
        ], options={'ordering': ['display_order', 'id']}),
        migrations.AddConstraint(model_name='postcontributor', constraint=models.UniqueConstraint(fields=('post', 'contributor', 'role'), name='unique_post_contributor_role')),
        migrations.RunPython(backfill_author_slugs_and_credits, migrations.RunPython.noop),
        migrations.AlterField(model_name='author', name='slug', field=models.SlugField(max_length=220, unique=True)),
        migrations.AlterField(model_name='author', name='created_at', field=models.DateTimeField(auto_now_add=True)),
        migrations.AlterField(model_name='author', name='updated_at', field=models.DateTimeField(auto_now=True)),
    ]
