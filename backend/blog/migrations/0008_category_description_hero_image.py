from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('blog', '0007_alter_author_options')]
    operations = [
        migrations.AddField(model_name='category', name='description', field=models.TextField(blank=True)),
        migrations.AddField(model_name='category', name='hero_image', field=models.URLField(blank=True, max_length=1000)),
    ]
