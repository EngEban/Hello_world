"""Read-only public content queries (T-20)."""

from django.utils import timezone


def published_post_count(category):
    return category.post_set.filter(post_type='post', status='publish', published_at__lte=timezone.now()).count()
