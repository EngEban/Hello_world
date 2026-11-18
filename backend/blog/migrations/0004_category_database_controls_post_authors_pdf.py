import django.core.validators
from django.db import migrations, models

import blog.models


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0003_alter_mediaasset_file'),
    ]

    operations = [
        migrations.AddField(
            model_name='category',
            name='database_order',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='category',
            name='show_in_database',
            field=models.BooleanField(default=True),
        ),
        migrations.AlterModelOptions(
            name='category',
            options={'ordering': ['database_order', 'name'], 'verbose_name_plural': 'Categories'},
        ),
        migrations.AddField(
            model_name='post',
            name='authors',
            field=models.ManyToManyField(blank=True, related_name='authored_posts', to='blog.author'),
        ),
        migrations.AddField(
            model_name='post',
            name='pdf_file',
            field=models.FileField(blank=True, null=True, upload_to=blog.models.uuid_upload_to, validators=[django.core.validators.FileExtensionValidator(allowed_extensions=['pdf'])]),
        ),
        migrations.AddField(
            model_name='post',
            name='pdf_title',
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
