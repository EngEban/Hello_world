from django.db import migrations, models
import django.db.models.deletion
from django.utils.text import slugify


DEFAULT_FAQ = {
    'About the Platform': [
        ('What is ResRef?', 'ResRef is a professional research reference platform that brings together validated questionnaires, methodology content, interactive tools, research opportunities, and expert support.'),
        ('Who is ResRef for?', 'ResRef is built for medical students, residents, clinicians, researchers, faculty members, and institutional research teams.'),
        ('Is ResRef free?', 'Core database browsing, tools, and expert consultation pathways are free for users. Future account features may add optional advanced access.'),
    ],
    'Research Database': [
        ('How do I find a questionnaire?', 'Use the database search bar to search by questionnaire name, topic, specialty, or keyword, then refine results using category filters.'),
        ('Are resources peer-reviewed?', 'ResRef prioritizes validated and source-linked questionnaires and research materials. Users should still verify final use against their institution or journal requirements.'),
    ],
    'Research Tools': [
        ('What tools are available?', 'The current tool hub includes the Sample Size Calculator and Reference Generator. Questionnaire Finder and Data Analysis Guide are planned as coming-soon tools.'),
        ('Are the tools free?', 'Yes. The research tools are designed as free support for students, clinicians, and researchers.'),
    ],
    'Expert Consultation': [
        ('Is consultation really free?', 'Yes. ResRef expert consultation is free for users at all research levels.'),
        ('How long does it take?', 'The team aims to respond within 48–72 hours depending on the request type and volume.'),
        ('What types of research do you support?', 'ResRef can support medical, health science, educational, public health, social, and related research projects.'),
    ],
    'Join Our Team': [
        ('What roles are available?', 'Open pathways include Education, Media, Design, IT, Data Entry, Quality Control, and Research Support roles.'),
        ('Do I need experience?', 'Some roles are beginner-friendly, while others need specialized research, design, technology, or quality review experience.'),
    ],
    'Technical Support': [
        ('I found an error in a questionnaire. How do I report it?', 'Use the Contact Us page and include the resource title, link, and the correction or concern you noticed.'),
        ("The website isn't loading. What should I do?", 'Refresh the page, check your connection, and contact ResRef if the issue continues. Include the page URL and a short description.'),
    ],
}


def seed_faq(apps, schema_editor):
    FAQCategory = apps.get_model('dashboard', 'FAQCategory')
    FAQItem = apps.get_model('dashboard', 'FAQItem')
    for category_order, (category_name, items) in enumerate(DEFAULT_FAQ.items(), start=10):
        category, created = FAQCategory.objects.get_or_create(
            slug=slugify(category_name),
            defaults={'name': category_name, 'sort_order': category_order},
        )
        if created:
            category.name = category_name
            category.sort_order = category_order
            category.save(update_fields=['name', 'sort_order'])
        for item_order, (question, answer) in enumerate(items, start=10):
            FAQItem.objects.get_or_create(
                category=category,
                question=question,
                defaults={
                    'answer': answer,
                    'status': 'published',
                    'sort_order': item_order,
                },
            )


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0003_researchopportunity_phase1_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='FAQCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('slug', models.SlugField(max_length=120, unique=True)),
                ('sort_order', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name_plural': 'FAQ categories',
                'ordering': ['sort_order', 'name'],
                'indexes': [models.Index(fields=['sort_order', 'name'], name='dashboard_f_sort_or_454ef3_idx')],
            },
        ),
        migrations.CreateModel(
            name='FAQItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('question', models.CharField(max_length=255)),
                ('answer', models.TextField()),
                ('status', models.CharField(choices=[('published', 'Published'), ('hidden', 'Hidden')], default='published', max_length=20)),
                ('sort_order', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='items', to='dashboard.faqcategory')),
            ],
            options={
                'ordering': ['category__sort_order', 'sort_order', 'question'],
                'indexes': [models.Index(fields=['status', 'sort_order'], name='dashboard_f_status_e8bc8e_idx'), models.Index(fields=['category', 'status', 'sort_order'], name='dashboard_f_categor_41b826_idx')],
            },
        ),
        migrations.RunPython(seed_faq, migrations.RunPython.noop),
    ]
