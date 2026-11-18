from django.apps import AppConfig


class LegacyRedirectsConfig(AppConfig):
    """Old-URL redirects and the WordPress import ledger.

    The label is not ``redirects`` so it can never clash with
    ``django.contrib.redirects`` if that is ever installed.
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'redirects'
    label = 'resref_redirects'
    verbose_name = 'Legacy redirects and WordPress import'

    def ready(self):
        from . import signals  # noqa: F401
