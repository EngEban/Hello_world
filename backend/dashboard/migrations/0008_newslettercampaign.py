from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('dashboard', '0007_seed_join_team_entries'),
    ]

    operations = [
        migrations.CreateModel(
            name='NewsletterCampaign',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('subject', models.CharField(max_length=160)),
                ('message', models.TextField()),
                ('status', models.CharField(choices=[('sent', 'Sent'), ('partial', 'Partially Sent'), ('failed', 'Failed')], default='sent', max_length=20)),
                ('recipient_count', models.PositiveIntegerField(default=0)),
                ('failed_count', models.PositiveIntegerField(default=0)),
                ('idempotency_key', models.CharField(blank=True, max_length=80, null=True, unique=True)),
                ('error_message', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('sent_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='newsletter_campaigns', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['status', 'created_at'], name='dashboard_n_status_27347c_idx'),
                    models.Index(fields=['sent_at'], name='dashboard_n_sent_at_388170_idx'),
                ],
            },
        ),
    ]
