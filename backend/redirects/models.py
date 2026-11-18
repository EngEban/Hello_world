from django.core.exceptions import ValidationError
from django.db import models

from .paths import normalize_path, safe_target


class Redirect(models.Model):
    """A permanent redirect from an old (usually WordPress) address."""

    STATUS_CODES = [(301, '301 Moved permanently'), (302, '302 Found (temporary)'), (307, '307 Temporary'), (308, '308 Permanent')]
    SOURCES = [
        ('manual', 'Added by staff'),
        ('wordpress', 'WordPress permalink'),
        ('wp_redirection', 'WordPress "Redirection" plugin'),
        ('rank_math', 'Rank Math redirections'),
    ]

    old_path = models.CharField(
        max_length=700, unique=True,
        help_text='Old address path, e.g. /2023/05/my-article/ (stored lower-case, without the trailing slash).',
    )
    new_url = models.CharField(max_length=1000, help_text='New path (/database/...) or full https:// URL.')
    status_code = models.PositiveSmallIntegerField(choices=STATUS_CODES, default=301)
    is_prefix = models.BooleanField(default=False, help_text='Redirect every address that starts with the old path, keeping the rest.')
    is_active = models.BooleanField(default=True)
    source = models.CharField(max_length=20, choices=SOURCES, default='manual')
    note = models.CharField(max_length=300, blank=True)
    hits = models.PositiveIntegerField(default=0)
    last_hit_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['old_path']

    def __str__(self):
        return f'{self.old_path} -> {self.new_url}'

    def clean(self):
        if normalize_path(self.old_path) == '/':
            raise ValidationError({'old_path': 'The home page cannot be redirected.'})
        if not safe_target(self.new_url):
            raise ValidationError({'new_url': 'Use a path starting with a single "/" or a full http(s):// URL.'})
        if normalize_path(self.old_path) == normalize_path(self.new_url):
            raise ValidationError({'new_url': 'A redirect cannot point to itself.'})

    def save(self, *args, **kwargs):
        self.old_path = normalize_path(self.old_path)
        super().save(*args, **kwargs)


class WordPressImportRecord(models.Model):
    """Ledger linking one WordPress object to the row it was imported into.

    ``field_hashes`` stores a fingerprint of each field value as last imported
    from WordPress, which lets a re-import tell "changed in WordPress" apart
    from "edited in the new dashboard" (three-way merge). Nothing here is ever
    deleted by the importer.
    """

    ENTITIES = [
        ('author', 'Author'), ('category', 'Category'), ('tag', 'Tag'), ('media', 'Media'),
        ('post', 'Post or page'), ('user', 'User account'), ('permalink', 'Old permalink redirect'),
        ('wp_redirection', 'Redirection plugin rule'), ('rank_math', 'Rank Math redirect rule'),
    ]

    entity = models.CharField(max_length=20, choices=ENTITIES)
    wordpress_id = models.BigIntegerField()
    object_id = models.CharField(max_length=64)
    field_hashes = models.JSONField(default=dict, blank=True)
    checksum = models.CharField(max_length=64, blank=True, help_text='SHA-256 of the copied media file.')
    source_format = models.CharField(max_length=10, blank=True)
    first_imported_at = models.DateTimeField(auto_now_add=True)
    last_imported_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['entity', 'wordpress_id']
        constraints = [models.UniqueConstraint(fields=['entity', 'wordpress_id'], name='unique_wordpress_import_record')]
        indexes = [models.Index(fields=['entity', 'object_id'])]

    def __str__(self):
        return f'{self.entity} wp#{self.wordpress_id} -> {self.object_id}'
