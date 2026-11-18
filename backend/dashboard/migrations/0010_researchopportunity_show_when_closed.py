from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0009_researchopportunity_custom_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='researchopportunity',
            name='show_when_closed',
            field=models.BooleanField(default=False),
        ),
    ]
