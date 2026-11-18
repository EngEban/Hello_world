import uuid

from django.db import models
from django.core.validators import FileExtensionValidator
from django.utils.text import slugify


def uuid_upload_to(instance, filename):
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    return f'uploads/{instance.__class__.__name__.lower()}/{uuid.uuid4()}.{ext}' if ext else f'uploads/{instance.__class__.__name__.lower()}/{uuid.uuid4()}'


class Author(models.Model):
    login = models.CharField(max_length=100, unique=True)
    display_name = models.CharField(max_length=200)
    email = models.EmailField(blank=True)
    role = models.CharField(max_length=120, blank=True)
    bio = models.TextField(blank=True)
    avatar = models.URLField(blank=True, max_length=1000)
    website = models.URLField(blank=True, max_length=1000)
    linkedin = models.URLField(blank=True, max_length=1000)
    twitter = models.URLField(blank=True, max_length=1000)
    wordpress_id = models.PositiveIntegerField(null=True, blank=True, unique=True)
    # `bio` remains the long, legacy-compatible biography.  `short_bio` is
    # deliberately separate for compact article cards.
    slug = models.SlugField(max_length=220, unique=True)
    prefix = models.CharField(max_length=40, blank=True)
    credentials = models.CharField(max_length=160, blank=True)
    position = models.CharField(max_length=200, blank=True)
    specialty = models.CharField(max_length=200, blank=True)
    institution = models.CharField(max_length=250, blank=True)
    country = models.CharField(max_length=120, blank=True)
    short_bio = models.TextField(blank=True)
    orcid = models.URLField(blank=True, max_length=1000)
    google_scholar = models.URLField(blank=True, max_length=1000)
    researchgate = models.URLField(blank=True, max_length=1000)
    profile_media = models.ForeignKey('MediaAsset', null=True, blank=True, on_delete=models.SET_NULL, related_name='contributor_profiles')
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    seo_title = models.CharField(max_length=500, blank=True)
    seo_description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'display_name', 'login']

    def __str__(self):
        return self.display_name

    def save(self, *args, **kwargs):
        """Keep programmatic/imported contributor records addressable too."""
        if not self.slug:
            base = slugify(self.display_name) or slugify(self.login) or 'contributor'
            candidate, number = base[:220], 2
            while Author.objects.exclude(pk=self.pk).filter(slug=candidate).exists():
                suffix = f'-{number}'
                candidate = f'{base[:220-len(suffix)]}{suffix}'
                number += 1
            self.slug = candidate
        super().save(*args, **kwargs)


class Category(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    hero_image = models.URLField(blank=True, max_length=1000)
    slug = models.SlugField(unique=True, max_length=200)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='children')
    show_in_database = models.BooleanField(default=True)
    database_order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['database_order', 'name']

    def __str__(self):
        return self.name


class Tag(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, max_length=200)

    def __str__(self):
        return self.name


class MediaAsset(models.Model):
    title = models.CharField(max_length=300, blank=True)
    alt_text = models.CharField(max_length=500, blank=True)
    caption = models.TextField(blank=True)
    url = models.URLField(blank=True, max_length=1500)
    file = models.ImageField(upload_to=uuid_upload_to, blank=True, null=True, validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'gif', 'webp'])])
    optimized_file = models.ImageField(upload_to=uuid_upload_to, blank=True, null=True, validators=[FileExtensionValidator(allowed_extensions=['webp'])])
    wordpress_id = models.PositiveIntegerField(null=True, blank=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return self.title or self.url or f'Media {self.pk}'

    def source_url(self):
        return self.optimized_file.url if self.optimized_file else self.file.url if self.file else self.url


class Post(models.Model):
    POST_TYPES = [('post', 'Post'), ('page', 'Page')]
    STATUSES = [('draft', 'Draft'), ('pending', 'Pending Review'), ('private', 'Private'), ('publish', 'Published'), ('trash', 'Trash')]

    title = models.CharField(max_length=500)
    slug = models.SlugField(unique=True, max_length=500)
    content = models.TextField()
    excerpt = models.TextField(blank=True)
    post_type = models.CharField(max_length=20, choices=POST_TYPES, default='post')
    status = models.CharField(max_length=20, choices=STATUSES, default='publish')
    author = models.ForeignKey(Author, null=True, blank=True, on_delete=models.SET_NULL)
    authors = models.ManyToManyField(Author, blank=True, related_name='authored_posts')
    categories = models.ManyToManyField(Category, blank=True)
    tags = models.ManyToManyField(Tag, blank=True)
    featured_image = models.URLField(blank=True, max_length=1000)
    pdf_file = models.FileField(upload_to=uuid_upload_to, blank=True, null=True, validators=[FileExtensionValidator(allowed_extensions=['pdf'])])
    pdf_title = models.CharField(max_length=255, blank=True)
    seo_title = models.CharField(max_length=500, blank=True)
    seo_description = models.TextField(blank=True)
    design_settings = models.JSONField(default=dict, blank=True)
    wordpress_id = models.PositiveIntegerField(null=True, blank=True, unique=True)
    wordpress_url = models.URLField(blank=True, max_length=1000)
    elementor_data = models.TextField(blank=True)
    page_template = models.CharField(max_length=200, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-published_at']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        from django.urls import reverse
        if self.post_type == 'page':
            return reverse('page_detail', kwargs={'slug': self.slug})
        return reverse('post_detail', kwargs={'slug': self.slug})


class PostContributor(models.Model):
    """A reusable contributor profile credited in a particular article."""
    ROLE_AUTHOR = 'author'
    ROLE_CHOICES = [
        (ROLE_AUTHOR, 'Author'),
        ('co_author', 'Co-author'),
        ('editor', 'Editor'),
        ('reviewer', 'Reviewer'),
        ('translator', 'Translator'),
        ('formatter', 'Formatter'),
    ]

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='contributor_assignments')
    contributor = models.ForeignKey(Author, on_delete=models.PROTECT, related_name='contributions')
    role = models.CharField(max_length=32, choices=ROLE_CHOICES, default=ROLE_AUTHOR)
    display_order = models.PositiveIntegerField(default=0)
    contribution_note = models.TextField(blank=True)

    class Meta:
        ordering = ['display_order', 'id']
        constraints = [
            models.UniqueConstraint(fields=['post', 'contributor', 'role'], name='unique_post_contributor_role'),
        ]

    def __str__(self):
        return f'{self.contributor} ({self.get_role_display()}) — {self.post}'
