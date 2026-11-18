# Generated for ResRef dashboard Phase 1 opportunities architecture.

import django.db.models.deletion
from django.db import migrations, models


def normalize_opportunity_statuses(apps, schema_editor):
    ResearchOpportunity = apps.get_model('dashboard', 'ResearchOpportunity')
    ResearchOpportunity.objects.filter(status='open').update(status='published')
    ResearchOpportunity.objects.filter(status='reviewing').update(status='draft')


def copy_legacy_descriptions(apps, schema_editor):
    ResearchOpportunity = apps.get_model('dashboard', 'ResearchOpportunity')
    for item in ResearchOpportunity.objects.all().only('id', 'eligibility', 'requirements'):
        if item.eligibility and not item.requirements:
            item.requirements = item.eligibility
            item.save(update_fields=['requirements'])


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0001_initial'),
        ('dashboard', '0002_servicedefinition_servicerequest_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='researchopportunity',
            name='benefits',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='researchopportunity',
            name='is_remote',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='researchopportunity',
            name='opportunity_type',
            field=models.CharField(choices=[('position', 'Position'), ('collaboration', 'Collaboration'), ('programme', 'Programme')], default='position', max_length=30),
        ),
        migrations.AddField(
            model_name='researchopportunity',
            name='organization',
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.AddField(
            model_name='researchopportunity',
            name='requirements',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='researchopportunity',
            name='specialty',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='research_opportunities', to='blog.category'),
        ),
        migrations.RunPython(normalize_opportunity_statuses, migrations.RunPython.noop),
        migrations.RunPython(copy_legacy_descriptions, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='researchopportunity',
            name='status',
            field=models.CharField(choices=[('draft', 'Draft'), ('published', 'Published'), ('closed', 'Closed'), ('archived', 'Archived')], default='draft', max_length=20),
        ),
        migrations.AddIndex(
            model_name='researchopportunity',
            index=models.Index(fields=['opportunity_type', 'status'], name='dashboard_r_opportu_4bc4ef_idx'),
        ),
        migrations.AddIndex(
            model_name='researchopportunity',
            index=models.Index(fields=['specialty', 'status'], name='dashboard_r_special_f61eb6_idx'),
        ),
    ]
