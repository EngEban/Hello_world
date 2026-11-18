from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0013_profile_country_phone_deleted'),
    ]

    operations = [
        migrations.AddField(
            model_name='accountrole',
            name='dashboard_permissions',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
