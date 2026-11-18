from django.core.cache import cache
from django.core.management.base import BaseCommand

from blog.models import Post
from blog.seo_analysis import cached_reports, report_key, site_host


class Command(BaseCommand):
    help = 'Analyse articles and pages for the dashboard SEO / AEO / GEO overview (results are cached).'

    def add_arguments(self, parser):
        parser.add_argument('--all', action='store_true', help='Re-analyse every post, not only those without a cached report.')

    def handle(self, *args, **options):
        queryset = Post.objects.exclude(status='trash')
        if options['all']:
            host = site_host()
            cache.delete_many([report_key(post, host) for post in queryset.defer('content', 'elementor_data').prefetch_related('categories', 'tags', 'authors', 'contributor_assignments')])
        reports, pending = cached_reports(queryset)
        self.stdout.write(self.style.SUCCESS(f'{len(reports)} posts analysed ({pending} pending).'))
