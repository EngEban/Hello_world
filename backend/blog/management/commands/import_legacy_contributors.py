"""Preview or recover named article credits; never infer an uploader."""
from django.core.management.base import BaseCommand, CommandError

from blog.legacy_credits import extract_profiles, restore_article_credits_v1
from blog.models import Author, Post, PostContributor


class Command(BaseCommand):
    help = 'Recover explicitly named legacy contributors. Dry run by default; source HTML and existing assignments are preserved.'

    def add_arguments(self, parser):
        scope = parser.add_mutually_exclusive_group(required=True)
        scope.add_argument('--slug')
        scope.add_argument('--all', action='store_true')
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        posts = Post.objects.filter(post_type='post').exclude(status='trash')
        if options.get('slug'):
            posts = posts.filter(slug=options['slug'])
            if not posts.exists():
                raise CommandError('Article not found.')
        total = 0
        for post in posts.iterator():
            if post.contributor_assignments.exists() or post.authors.exists():
                self.stdout.write(f'{post.slug}: assigned contributors preserved.')
                if options['apply']:
                    restore_article_credits_v1(post, Author, PostContributor)
                continue
            profiles = extract_profiles(post.content)
            if not profiles:
                continue
            for profile in profiles:
                self.stdout.write(f"{post.slug}: {profile['name']} — {profile['role_text']}")
            total += len(profiles)
            if options['apply']:
                restore_article_credits_v1(post, Author, PostContributor)
        mode = 'Recovered' if options['apply'] else 'Preview'
        self.stdout.write(self.style.SUCCESS(f'{mode}: {total} named role credits. Source HTML, dates and per-article opt-outs preserved.'))
