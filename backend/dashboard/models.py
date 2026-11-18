import uuid
import re

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import FileExtensionValidator
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from django.utils.text import slugify

from blog.models import Category, MediaAsset


ALLOWED_CV_EXTENSIONS = ['pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png']
ALLOWED_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp']


def uuid_upload_to(instance, filename):
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    return f'uploads/{instance.__class__.__name__.lower()}/{uuid.uuid4()}.{ext}' if ext else f'uploads/{instance.__class__.__name__.lower()}/{uuid.uuid4()}'


class ContactSubmission(models.Model):
    STATUS = [('new','New'),('read','Read'),('replied','Replied'),('archived','Archived')]
    name        = models.CharField(max_length=200)
    company     = models.CharField(max_length=200, blank=True)
    whatsapp    = models.CharField(max_length=50, blank=True)
    email       = models.EmailField()
    specialization = models.CharField(max_length=200, blank=True)
    message     = models.TextField()
    status      = models.CharField(max_length=20, choices=STATUS, default='new')
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} — {self.created_at.strftime('%d %b %Y')}"


class JobApplication(models.Model):
    TEAMS = [
        ('education','Education Team'),('media','Media Team'),('design','Design Team'),
        ('it','IT Team'),('data_entry','Data Entry Team'),('quality','Quality Control Team'),
        ('web_seo','Web & SEO Team'),('community','Community Team'),('other','Other'),
    ]
    STATUS = [('new','New'),('reviewing','Reviewing'),('interview','Interview'),('accepted','Accepted'),('rejected','Rejected')]

    full_name   = models.CharField(max_length=200)
    email       = models.EmailField()
    whatsapp    = models.CharField(max_length=50, blank=True)
    team        = models.CharField(max_length=50, choices=TEAMS)
    experience  = models.TextField(blank=True)
    motivation  = models.TextField(blank=True)
    portfolio   = models.URLField(blank=True)
    cv_file     = models.FileField(upload_to=uuid_upload_to, blank=True, null=True, validators=[FileExtensionValidator(allowed_extensions=ALLOWED_CV_EXTENSIONS)])
    status      = models.CharField(max_length=20, choices=STATUS, default='new')
    notes       = models.TextField(blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.full_name} — {self.get_team_display()}"


class NewsletterSubscriber(models.Model):
    email      = models.EmailField(unique=True)
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # Double opt-in: a public sign-up stays inactive with confirmed_at=None
    # until the emailed link is used. Only confirmed, active rows get mail.
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmation_token_hash = models.CharField(max_length=128, blank=True, db_index=True)
    confirmation_sent_at = models.DateTimeField(null=True, blank=True)

    @property
    def is_pending(self):
        return self.confirmed_at is None

    def __str__(self):
        return self.email


class NewsletterCampaign(models.Model):
    STATUS = [
        ('queued', 'Queued'),
        ('sending', 'Sending'),
        ('sent', 'Sent'),
        ('partial', 'Partially Sent'),
        ('failed', 'Failed'),
    ]

    subject = models.CharField(max_length=160)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS, default='sent')
    recipient_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    idempotency_key = models.CharField(max_length=80, unique=True, null=True, blank=True)
    error_message = models.TextField(blank=True)
    sent_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='newsletter_campaigns')
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['sent_at']),
        ]

    def __str__(self):
        return f'{self.subject} / {self.get_status_display()}'


class NewsletterDelivery(models.Model):
    """One recipient of a campaign. Sent by ``manage.py process_outbox`` so a
    large send never runs inside a web request and resumes after a crash."""

    STATUS = [
        ('pending', 'Pending'),
        ('claimed', 'Being sent'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
    ]

    campaign = models.ForeignKey(NewsletterCampaign, on_delete=models.CASCADE, related_name='deliveries')
    email = models.EmailField()
    status = models.CharField(max_length=20, choices=STATUS, default='pending')
    attempts = models.PositiveSmallIntegerField(default=0)
    claim_token = models.CharField(max_length=40, blank=True)
    claimed_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    error_message = models.CharField(max_length=500, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['campaign', 'email'], name='newsletter_delivery_unique_recipient'),
        ]
        indexes = [models.Index(fields=['campaign', 'status'])]

    def __str__(self):
        return f'{self.email} / {self.status}'


class TeamMember(models.Model):
    ROLES = [
        ('admin','Admin'),('editor','Editor'),('contributor','Contributor'),('viewer','Viewer')
    ]
    user        = models.OneToOneField(User, on_delete=models.CASCADE, related_name='team_member')
    role        = models.CharField(max_length=20, choices=ROLES, default='contributor')
    department  = models.CharField(max_length=100, blank=True)
    bio         = models.TextField(blank=True)
    avatar      = models.ImageField(upload_to=uuid_upload_to, blank=True, null=True, validators=[FileExtensionValidator(allowed_extensions=ALLOWED_IMAGE_EXTENSIONS)])
    whatsapp    = models.CharField(max_length=50, blank=True)
    is_active   = models.BooleanField(default=True)
    joined_at   = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.get_role_display()})"


class TeamPageSettings(models.Model):
    """The public Team page as a whole: a single row. It stays unpublished until
    a Super Admin publishes it, whatever the state of its sections and members."""

    hero_title = models.CharField(max_length=160, default='Our Team')
    hero_text = models.TextField(blank=True)
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Team page settings'

    def __str__(self):
        return 'Team page'

    @classmethod
    def load(cls):
        return cls.objects.get_or_create(pk=1)[0]

    @classmethod
    def is_live(cls):
        return cls.objects.filter(pk=1, is_published=True).exists()


class TeamPageSection(models.Model):
    # The level sets the visual weight on the page, independent of its position.
    LEVELS = [
        ('founder', 'Founder spotlight'),
        ('leadership', 'Leadership'),
        ('directors', 'Directors'),
        ('team', 'Team'),
    ]

    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    level = models.CharField(max_length=20, choices=LEVELS, default='team')
    is_visible = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'id']

    def __str__(self):
        return self.name


class TeamPageMember(models.Model):
    """A person shown on the public Team page. Separate from TeamMember, which
    is a dashboard sign-in account."""

    STATUS = [('draft', 'Draft'), ('published', 'Published')]

    section = models.ForeignKey(TeamPageSection, on_delete=models.PROTECT, related_name='members')
    full_name = models.CharField(max_length=150)
    role = models.CharField(max_length=150, blank=True)
    department = models.CharField(max_length=120, blank=True)
    bio = models.TextField(blank=True)
    vision = models.TextField(blank=True)
    photo = models.ForeignKey(MediaAsset, null=True, blank=True, on_delete=models.SET_NULL, related_name='team_page_members')
    links = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default='draft')
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'id']

    def __str__(self):
        return self.full_name


class JoinTeamEntry(models.Model):
    ICONS = [
        ('pen', 'Education / Writing'),
        ('megaphone', 'Media'),
        ('palette', 'Design'),
        ('code', 'Technology'),
        ('chart', 'Data'),
        ('search', 'Quality Control'),
        ('users', 'Web / SEO'),
        ('briefcase', 'General Role'),
    ]
    STATUS = [('published', 'Published'), ('draft', 'Draft'), ('archived', 'Archived')]

    title = models.CharField(max_length=120)
    slug = models.SlugField(max_length=150, unique=True, blank=True)
    description = models.TextField(max_length=500)
    icon_key = models.CharField(max_length=30, choices=ICONS, default='briefcase')
    action_label = models.CharField(max_length=80, default='Apply to join')
    action_url = models.CharField(max_length=1000, default='#team-application')
    status = models.CharField(max_length=20, choices=STATUS, default='published')
    sort_order = models.PositiveIntegerField(default=0)
    seo_title = models.CharField(max_length=70, blank=True)
    seo_description = models.CharField(max_length=170, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'title']
        indexes = [
            models.Index(fields=['status', 'sort_order']),
            models.Index(fields=['slug']),
        ]

    def clean(self):
        self.title = (self.title or '').strip()
        self.description = (self.description or '').strip()
        self.action_label = (self.action_label or '').strip()
        self.action_url = (self.action_url or '').strip()
        if not self.title:
            raise ValidationError({'title': 'Team title is required.'})
        if not self.description:
            raise ValidationError({'description': 'Team description is required.'})
        if not self.action_label:
            raise ValidationError({'action_label': 'Button label is required.'})
        if not self.action_url:
            raise ValidationError({'action_url': 'Button link is required.'})
        if self.action_url.startswith('#'):
            if not self.action_url[1:].replace('-', '').replace('_', '').isalnum():
                raise ValidationError({'action_url': 'Anchor links can only contain letters, numbers, hyphens, and underscores.'})
            return
        URLValidator(schemes=['http', 'https'])(self.action_url)

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)[:120] or 'team'
            slug = base
            counter = 2
            while JoinTeamEntry.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base}-{counter}'
                counter += 1
            self.slug = slug
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class SiteSettings(models.Model):
    # This table is public configuration only. Credentials belong in environment
    # variables and must never be persisted here.
    # Explicitly reviewed public configuration keys. Adding a public setting
    # requires updating this list; arbitrary rows never become public by default.
    PUBLIC_SETTING_KEYS = frozenset('''
        article_hero_image_url article_related_title article_toc_title article_download_text
        contributors_hero_text contributors_hero_image_url footer_logo_url
        database_search_placeholder database_search_button_label database_results_title
        database_count_label database_empty_title database_empty_text
        nav_database_label nav_tools_label nav_opportunities_label nav_consultation_label
        nav_learn_label nav_join_label nav_contact_label nav_about_label
        research_analyzer_hero_title research_analyzer_hero_text research_analyzer_hero_image_url
        site_name contact_email contact_phone contact_address social_links logo_url
        whatsapp_label whatsapp_url telegram_url footer_description page_banner_image_url
        page_hero_title_size page_hero_text_size page_hero_title_weight page_hero_text_weight
        home_gateway_title home_gateway_text home_hero_image_url home_hero_title home_hero_text
        home_hero_title_size home_hero_text_size home_hero_title_weight home_primary_cta_label
        home_primary_cta_url home_secondary_cta_label home_secondary_cta_url home_stat_1_value
        home_stat_1_label home_stat_2_value home_stat_2_label home_stat_3_value home_stat_3_label
        home_stat_4_value home_stat_4_label home_quick_access_enabled home_quick_1_title
        home_quick_1_text home_quick_1_url home_quick_2_title home_quick_2_text home_quick_2_url
        home_quick_3_title home_quick_3_text home_quick_3_url home_quick_4_title home_quick_4_text
        home_quick_4_url home_pathways_enabled home_pathways_eyebrow home_pathways_title
        home_pathways_text home_pathway_1_title home_pathway_1_text home_pathway_1_action
        home_pathway_1_url home_pathway_2_title home_pathway_2_text home_pathway_2_action
        home_pathway_2_url home_pathway_3_title home_pathway_3_text home_pathway_3_action
        home_pathway_3_url home_pathway_4_title home_pathway_4_text home_pathway_4_action
        home_pathway_4_url home_tools_enabled home_tools_label home_tools_title home_tools_text
        home_tools_cta_label home_tools_cta_url home_tools_image_url home_audience_enabled
        home_audience_eyebrow home_audience_title home_audience_text home_audience_image_url
        home_partners_enabled home_partners_eyebrow home_partners_title home_trust_enabled
        home_trust_eyebrow home_trust_title home_contact_enabled home_contact_eyebrow
        home_contact_title home_contact_text database_hero_title database_hero_text
        database_hero_image_url database_categories_label database_categories_title database_categories_text
        database_methodology_title database_methodology_text database_methodology_link_label
        database_methodology_link_url database_guidance_enabled database_guidance_title database_guidance_text
        database_guidance_link_label database_guidance_link_url database_support_enabled database_support_title
        database_support_text database_support_link_label database_support_link_url database_bottom_cta_title
        database_bottom_cta_text database_bottom_cta_label database_bottom_cta_url learn_hero_title
        learn_hero_text learn_hero_image_url learn_page_label learn_page_title learn_page_text
        learn_category_label learn_category_slug learn_search_placeholder learn_search_button_label
        learn_results_title learn_empty_title learn_empty_text learn_count_label tools_hero_title
        tools_hero_text tools_hero_image_url tools_hub_eyebrow tools_hub_title tools_hub_text
        tools_guidance_cta_label tools_guidance_cta_url tools_bottom_cta_title tools_bottom_cta_text
        tools_bottom_cta_label tools_bottom_cta_url tools_workflow_1_title tools_workflow_1_text
        tools_workflow_2_title tools_workflow_2_text tools_workflow_3_title tools_workflow_3_text
        consultation_hero_title consultation_hero_text consultation_hero_image_url consultation_overview_eyebrow
        consultation_overview_title consultation_overview_text consultation_overview_image_url
        consultation_form_url consultation_form_button_label opportunities_hero_title
        opportunities_hero_text opportunities_hero_image_url opportunities_benefits_eyebrow
        opportunities_benefits_title opportunities_benefits_text opportunities_list_eyebrow
        opportunities_list_title opportunities_empty_title opportunities_empty_text opportunities_empty_button_label
        opportunities_empty_button_url opportunities_application_eyebrow opportunities_application_title
        opportunities_application_text opportunities_application_submit_label join_hero_title join_hero_text
        join_hero_image_url join_teams_eyebrow join_teams_title join_teams_text join_team_action_label
        join_team_action_url join_expect_title join_expect_1_title join_expect_1_text join_expect_2_title
        join_expect_2_text join_expect_3_title join_expect_3_text join_expect_help_text join_expect_help_link about_hero_title about_hero_text about_hero_image_url about_identity_eyebrow
        about_identity_title about_identity_text about_identity_body about_identity_image_url about_mission_title
        about_mission_text about_values_eyebrow about_values_title about_values_text about_audience_eyebrow
        about_audience_title about_audience_text about_audience_link_label about_audience_link_url
        contact_hero_title contact_hero_text contact_hero_image_url contact_command_eyebrow contact_command_title
        contact_command_text contact_route_action_label contact_form_title contact_form_text
        contact_form_submit_label contact_form_message_placeholder contact_direct_label contact_direct_title
        contact_direct_text contact_process_eyebrow contact_process_title contact_process_text faq_hero_title
        faq_hero_text faq_hero_image_url faq_command_eyebrow faq_command_title faq_command_text
        faq_search_placeholder faq_support_eyebrow faq_support_title faq_support_text journal_finder_hero_title
        journal_finder_hero_text journal_finder_hero_image_url sample_size_hero_title sample_size_hero_text
        sample_size_hero_image_url questionnaires_hero_title questionnaires_hero_text questionnaires_hero_image_url
        reference_generator_hero_title reference_generator_hero_text reference_generator_hero_image_url
        not_found_hero_title not_found_hero_text not_found_hero_image_url
        homepage_hero_visible homepage_hero_order homepage_hero_kicker homepage_hero_title homepage_hero_text
        homepage_hero_footnote homepage_hero_primary_label homepage_hero_primary_url homepage_hero_secondary_label
        homepage_hero_secondary_url homepage_hero_image_url homepage_hero_title_size homepage_hero_text_size
        homepage_hero_title_weight homepage_database_visible homepage_database_order homepage_database_label
        homepage_database_title homepage_database_text homepage_database_search_placeholder homepage_database_search_button_label
        homepage_database_support_text homepage_database_category_label homepage_database_resource_label
        homepage_database_tools_label homepage_database_retry_label homepage_database_unavailable_text
        homepage_learning_visible homepage_learning_order homepage_learning_label homepage_learning_title
        homepage_learning_text homepage_learning_action_label homepage_learning_action_url homepage_learning_empty_text
        homepage_tools_visible homepage_tools_order homepage_tools_label homepage_tools_title homepage_tools_text
        homepage_tools_detail_label homepage_tools_1_title homepage_tools_1_text homepage_tools_1_action homepage_tools_1_url
        homepage_tools_2_title homepage_tools_2_text homepage_tools_2_action homepage_tools_2_url homepage_tools_3_title
        homepage_tools_3_text homepage_tools_3_action homepage_tools_3_url homepage_tools_4_title homepage_tools_4_text
        homepage_tools_4_action homepage_tools_4_url homepage_tools_action_label homepage_tools_action_url
        homepage_tools_signed_in_note homepage_tools_signed_out_note homepage_consultations_visible homepage_consultations_order
        homepage_consultations_label homepage_consultations_title homepage_consultations_text homepage_consultations_1_title
        homepage_consultations_1_text homepage_consultations_2_title homepage_consultations_2_text homepage_consultations_3_title
        homepage_consultations_3_text homepage_consultations_4_title homepage_consultations_4_text homepage_consultations_action_label
        homepage_consultations_action_url homepage_opportunities_visible homepage_opportunities_order homepage_opportunities_label
        homepage_opportunities_title homepage_opportunities_text homepage_opportunities_board_label homepage_opportunities_empty_title
        homepage_opportunities_empty_text homepage_opportunities_fallback_text homepage_opportunities_remote_label
        homepage_opportunities_location_fallback homepage_opportunities_updated_label homepage_opportunities_action_label
        homepage_opportunities_action_url homepage_ecosystem_visible homepage_ecosystem_order homepage_ecosystem_label
        homepage_ecosystem_title homepage_ecosystem_text homepage_ecosystem_learning_title homepage_ecosystem_learning_text
        homepage_ecosystem_learning_action_label homepage_ecosystem_learning_action_url homepage_ecosystem_workspace_title
        homepage_ecosystem_workspace_text homepage_ecosystem_workspace_action_label homepage_ecosystem_workspace_action_url
        homepage_ecosystem_contribute_title homepage_ecosystem_contribute_text homepage_ecosystem_contribute_action_label
        homepage_ecosystem_contribute_action_url homepage_community_visible homepage_community_order homepage_community_label
        homepage_community_title homepage_community_text homepage_community_primary_label homepage_community_primary_url
        homepage_community_secondary_label homepage_community_secondary_url homepage_community_diagram_label homepage_community_diagram_question
        homepage_community_diagram_method homepage_community_diagram_evidence homepage_community_diagram_collaboration
        homepage_community_diagram_impact homepage_telegram_visible homepage_telegram_order homepage_telegram_label
        homepage_telegram_title homepage_telegram_text homepage_telegram_point_1 homepage_telegram_point_2
        homepage_telegram_point_3 homepage_telegram_button_label homepage_telegram_button_url homepage_telegram_bot_label
        homepage_telegram_bot_url homepage_telegram_image_url homepage_telegram_image_alt homepage_contact_visible
        homepage_contact_order homepage_contact_label homepage_contact_title homepage_contact_text homepage_contact_primary_label
        homepage_contact_primary_url homepage_contact_secondary_label homepage_contact_secondary_url
    '''.split())
    SENSITIVE_KEY_PATTERN = re.compile(r'(secret|key|token|password)', re.IGNORECASE)

    key   = models.CharField(max_length=100, unique=True)
    value = models.TextField(blank=True)
    label = models.CharField(max_length=200, blank=True)
    group = models.CharField(max_length=100, default='general')

    class Meta:
        verbose_name_plural = 'Site Settings'

    def __str__(self):
        return f"{self.group} / {self.key}"

    @classmethod
    def is_sensitive_key(cls, key):
        return bool(cls.SENSITIVE_KEY_PATTERN.search(key or ''))

    @classmethod
    def get(cls, key, default=''):
        try:
            return cls.objects.get(key=key).value
        except cls.DoesNotExist:
            return default


class DashboardActivityLog(models.Model):
    ACTIONS = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('status', 'Status Change'),
        ('login', 'Login'),
        ('export', 'Export'),
        ('system', 'System'),
    ]

    actor = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='dashboard_activity')
    action = models.CharField(max_length=30, choices=ACTIONS)
    module = models.CharField(max_length=80)
    object_id = models.CharField(max_length=80, blank=True)
    object_label = models.CharField(max_length=255, blank=True)
    message = models.CharField(max_length=500)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['module', 'created_at']),
            models.Index(fields=['actor', 'created_at']),
            models.Index(fields=['action', 'created_at']),
        ]

    def __str__(self):
        return f'{self.module} / {self.action} / {self.object_label or self.object_id}'


class ResearchOpportunity(models.Model):
    STATUS = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('closed', 'Closed'),
        ('archived', 'Archived'),
    ]
    TYPES = [
        ('position', 'Position'),
        ('collaboration', 'Collaboration'),
        ('programme', 'Programme'),
    ]
    PRIORITIES = [('low', 'Low'), ('normal', 'Normal'), ('high', 'High'), ('urgent', 'Urgent')]

    title = models.CharField(max_length=300)
    slug = models.SlugField(max_length=320, unique=True)
    organization = models.CharField(max_length=150, blank=True)
    opportunity_type = models.CharField(max_length=30, choices=TYPES, default='position')
    specialty = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL, related_name='research_opportunities')
    summary = models.TextField(blank=True)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default='draft')
    priority = models.CharField(max_length=20, choices=PRIORITIES, default='normal')
    location = models.CharField(max_length=200, blank=True)
    is_remote = models.BooleanField(default=False)
    eligibility = models.TextField(blank=True)
    requirements = models.TextField(blank=True)
    benefits = models.TextField(blank=True)
    custom_fields = models.JSONField(default=list, blank=True)
    application_url = models.URLField(blank=True, max_length=1000)
    contact_email = models.EmailField(blank=True)
    deadline = models.DateField(null=True, blank=True)
    is_featured = models.BooleanField(default=False)
    show_when_closed = models.BooleanField(default=False)
    assigned_to = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='assigned_research_opportunities')
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_research_opportunities')
    internal_notes = models.TextField(blank=True)
    seo_title = models.CharField(max_length=300, blank=True)
    seo_description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['status', 'deadline']),
            models.Index(fields=['category', 'status']),
            models.Index(fields=['is_featured', 'status']),
            models.Index(fields=['opportunity_type', 'status'], name='dashboard_r_opportu_4bc4ef_idx'),
            models.Index(fields=['specialty', 'status'], name='dashboard_r_special_f61eb6_idx'),
        ]

    def ensure_slug(self):
        """Populate a unique slug before validation or persistence.

        The dashboard supports leaving the slug empty.  Validation must honour
        that promise as well as ``save()``, otherwise ``full_clean()`` rejects
        a valid new opportunity before the automatic slug is created.
        """
        if not self.slug:
            base = slugify(self.title)[:280] or 'research-opportunity'
            slug = base
            counter = 2
            while ResearchOpportunity.objects.exclude(pk=self.pk).filter(slug=slug).exists():
                slug = f'{base}-{counter}'
                counter += 1
            self.slug = slug

    def save(self, *args, **kwargs):
        self.ensure_slug()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class FAQCategory(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True)
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name_plural = 'FAQ categories'
        indexes = [
            models.Index(fields=['sort_order', 'name'], name='dashboard_f_sort_or_454ef3_idx'),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:100] or 'faq-category'
            slug = base
            counter = 2
            while FAQCategory.objects.exclude(pk=self.pk).filter(slug=slug).exists():
                slug = f'{base}-{counter}'
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class FAQItem(models.Model):
    STATUS = [('published', 'Published'), ('hidden', 'Hidden')]

    category = models.ForeignKey(FAQCategory, on_delete=models.PROTECT, related_name='items')
    question = models.CharField(max_length=255)
    answer = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS, default='published')
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category__sort_order', 'sort_order', 'question']
        indexes = [
            models.Index(fields=['status', 'sort_order'], name='dashboard_f_status_e8bc8e_idx'),
            models.Index(fields=['category', 'status', 'sort_order'], name='dashboard_f_categor_41b826_idx'),
        ]

    def __str__(self):
        return self.question


class ServiceDefinition(models.Model):
    STATUS = [('active', 'Active'), ('paused', 'Paused'), ('archived', 'Archived')]

    title = models.CharField(max_length=240)
    slug = models.SlugField(max_length=260, unique=True)
    summary = models.TextField(blank=True)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default='active')
    assigned_team = models.CharField(max_length=120, blank=True)
    price_note = models.CharField(max_length=200, blank=True)
    turnaround_time = models.CharField(max_length=120, blank=True)
    intake_schema = models.JSONField(default=dict, blank=True)
    is_featured = models.BooleanField(default=False)
    internal_notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_services')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['title']
        indexes = [
            models.Index(fields=['status', 'category']),
            models.Index(fields=['is_featured', 'status']),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)[:220] or 'service'
            slug = base
            counter = 2
            while ServiceDefinition.objects.exclude(pk=self.pk).filter(slug=slug).exists():
                slug = f'{base}-{counter}'
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class ServiceRequest(models.Model):
    STATUS = [
        ('new', 'New'),
        ('reviewing', 'Reviewing'),
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('archived', 'Archived'),
    ]
    PRIORITIES = [('low', 'Low'), ('normal', 'Normal'), ('high', 'High'), ('urgent', 'Urgent')]

    service = models.ForeignKey(ServiceDefinition, null=True, blank=True, on_delete=models.SET_NULL, related_name='requests')
    requester_name = models.CharField(max_length=200)
    requester_email = models.EmailField()
    organization = models.CharField(max_length=250, blank=True)
    subject = models.CharField(max_length=300)
    message = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default='new')
    priority = models.CharField(max_length=20, choices=PRIORITIES, default='normal')
    assigned_to = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='assigned_service_requests')
    internal_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['assigned_to', 'status']),
            models.Index(fields=['service', 'status']),
        ]

    def __str__(self):
        return f'{self.subject} / {self.requester_name}'
