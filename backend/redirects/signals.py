from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .cache import bump_version
from .models import Redirect


@receiver(post_save, sender=Redirect)
@receiver(post_delete, sender=Redirect)
def invalidate_redirect_cache(sender, **kwargs):
    bump_version()
