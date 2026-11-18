from django.db import migrations


JOIN_TEAMS = [
    ('Education Team', 'education-team', 'Create educational materials and help make research knowledge easier to access.', 'pen', 10),
    ('Media Team', 'media-team', 'Share ResRef activities and research content with a growing community.', 'megaphone', 20),
    ('Design Team', 'design-team', 'Transform ideas into clear, engaging, and useful visual materials.', 'palette', 30),
    ('IT Team', 'it-team', 'Build and improve the digital tools behind the ResRef platform.', 'code', 40),
    ('Data Entry Team', 'data-entry-team', 'Organize resources and keep the database accurate and accessible.', 'chart', 50),
    ('Quality Control Team', 'quality-control-team', 'Review content and support a consistent standard of quality.', 'search', 60),
    ('Web & SEO Team', 'web-seo-team', 'Help researchers discover valuable content through a stronger web presence.', 'users', 70),
]


def seed_join_teams(apps, schema_editor):
    JoinTeamEntry = apps.get_model('dashboard', 'JoinTeamEntry')
    for title, slug, description, icon_key, sort_order in JOIN_TEAMS:
        JoinTeamEntry.objects.update_or_create(
            slug=slug,
            defaults={
                'title': title,
                'description': description,
                'icon_key': icon_key,
                'action_label': 'Apply to join',
                'action_url': '#team-application',
                'status': 'published',
                'sort_order': sort_order,
                'seo_title': f'{title} | Join ResRef',
                'seo_description': description[:170],
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0006_jointeamentry'),
    ]

    operations = [
        migrations.RunPython(seed_join_teams, migrations.RunPython.noop),
    ]
