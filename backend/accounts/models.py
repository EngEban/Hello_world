from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class AccountRole(models.Model):
    code = models.SlugField(max_length=50, unique=True)
    label = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    can_access_dashboard = models.BooleanField(default=False)
    is_super_admin = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    # Dashboard permission codes (``module.action``) this role grants; edited
    # on the dashboard's Roles & Permissions page. See dashboard.permissions.
    dashboard_permissions = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return self.label


class MembershipProfile(models.Model):
    TIERS = [('free', 'Free'), ('premium', 'Premium')]
    ROLES = [('member', 'Member'), ('editor', 'Editor'), ('admin', 'Administrator')]
    PROVIDERS = [('password', 'Email and Password'), ('google', 'Google')]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='membership_profile')
    account_role = models.ForeignKey('AccountRole', null=True, blank=True, on_delete=models.SET_NULL, related_name='profiles')
    plan = models.ForeignKey('SubscriptionPlan', null=True, blank=True, on_delete=models.SET_NULL, related_name='profiles')
    tier = models.CharField(max_length=20, choices=TIERS, default='free')
    access_role = models.CharField(max_length=20, choices=ROLES, default='member')
    auth_provider = models.CharField(max_length=20, choices=PROVIDERS, default='password')
    google_subject = models.CharField(max_length=255, unique=True, null=True, blank=True)
    email_verified = models.BooleanField(default=False)
    # Set for accounts created through self-registration: they cannot sign in
    # with a password until the emailed link is used (accounts that existed
    # before this rule stay False and are not locked out).
    email_confirmation_required = models.BooleanField(default=False)
    display_name = models.CharField(max_length=200, blank=True)
    avatar_url = models.URLField(max_length=1000, blank=True)
    organization = models.CharField(max_length=250, blank=True)
    specialization = models.CharField(max_length=250, blank=True)
    premium_until = models.DateTimeField(null=True, blank=True)
    marketing_opt_in = models.BooleanField(default=False)
    # ISO 3166-1 alpha-2 code (validated in accounts.profile_fields).
    country = models.CharField(max_length=2, blank=True, default='')
    # International number in E.164 form, e.g. +447911123456.
    phone_number = models.CharField(max_length=16, blank=True, default='')
    # Set when the member deleted their account: personal data was removed and
    # the login deactivated, while records other data depends on are kept.
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.user.username} / {self.effective_tier}'

    @property
    def effective_tier(self):
        if self.tier == 'premium' and (not self.premium_until or self.premium_until > timezone.now()):
            return 'premium'
        return 'free'

    @property
    def can_access_dashboard(self):
        if not self.user.is_active:
            return False
        if self.account_role_id and self.account_role.is_active and self.account_role.can_access_dashboard:
            return True
        return self.user.is_staff and self.access_role in {'editor', 'admin'}


class SubscriptionPlan(models.Model):
    PROVIDERS = [('manual', 'Manual'), ('stripe', 'Stripe')]
    INTERVALS = [('none', 'None'), ('month', 'Monthly'), ('year', 'Yearly')]

    code = models.SlugField(max_length=80, unique=True)
    label = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    tier = models.CharField(max_length=20, choices=MembershipProfile.TIERS, default='free')
    provider = models.CharField(max_length=20, choices=PROVIDERS, default='manual')
    provider_price_id = models.CharField(max_length=255, blank=True)
    billing_interval = models.CharField(max_length=20, choices=INTERVALS, default='none')
    price_cents = models.PositiveIntegerField(default=0)
    currency = models.CharField(max_length=10, default='USD')
    is_public = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['price_cents', 'label']

    def __str__(self):
        return self.label


class UserSubscription(models.Model):
    STATUSES = [
        ('trialing', 'Trialing'),
        ('incomplete', 'Incomplete'),
        ('active', 'Active'),
        ('past_due', 'Past Due'),
        ('unpaid', 'Unpaid'),
        ('canceled', 'Canceled'),
        ('expired', 'Expired'),
        ('manual', 'Manual Grant'),
    ]
    PROVIDERS = [('manual', 'Manual'), ('stripe', 'Stripe')]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subscriptions')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name='subscriptions')
    status = models.CharField(max_length=20, choices=STATUSES, default='manual')
    provider = models.CharField(max_length=20, choices=PROVIDERS, default='manual')
    provider_customer_id = models.CharField(max_length=255, blank=True)
    provider_subscription_id = models.CharField(max_length=255, blank=True)
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['provider', 'provider_subscription_id']),
            models.Index(fields=['provider', 'provider_customer_id']),
            models.Index(fields=['current_period_end']),
        ]

    def __str__(self):
        return f'{self.user.email or self.user.username} / {self.plan.code} / {self.status}'

    @property
    def is_current(self):
        if self.status not in {'trialing', 'active', 'manual'}:
            return False
        return not self.current_period_end or self.current_period_end > timezone.now()


class BillingWebhookEvent(models.Model):
    provider = models.CharField(max_length=20, default='stripe')
    event_id = models.CharField(max_length=255, unique=True)
    event_type = models.CharField(max_length=120)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['provider', 'event_type']),
            models.Index(fields=['processed_at']),
        ]

    def __str__(self):
        return f'{self.provider} / {self.event_type} / {self.event_id}'


class AccountNotification(models.Model):
    TYPES = [
        ('info', 'Information'),
        ('billing', 'Billing'),
        ('security', 'Security'),
        ('opportunity', 'Opportunity'),
        ('announcement', 'Announcement'),
    ]

    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE, related_name='account_notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=30, choices=TYPES, default='info')
    action_url = models.CharField(max_length=500, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    # Set on system broadcasts (user=None) so one event never creates two rows,
    # e.g. "opportunity-published:<id>".
    dedupe_key = models.CharField(max_length=120, unique=True, null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read', 'created_at']),
            models.Index(fields=['notification_type', 'created_at']),
        ]

    def __str__(self):
        scope = self.user.email if self.user_id and self.user.email else 'announcement'
        return f'{scope} / {self.title}'

    def mark_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])


class AccountNotificationRead(models.Model):
    """Per-user read state for broadcast notifications (user=None rows)."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notification_reads')
    notification = models.ForeignKey(AccountNotification, on_delete=models.CASCADE, related_name='reads')
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'notification'], name='account_notification_read_once'),
        ]


class FeatureEntitlement(models.Model):
    code = models.SlugField(max_length=100, unique=True)
    label = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    free_enabled = models.BooleanField(default=False)
    premium_enabled = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['label']

    def __str__(self):
        return self.label

    def allows(self, profile):
        if not self.is_active:
            return False
        return self.premium_enabled if profile.effective_tier == 'premium' else self.free_enabled


class UsageLimit(models.Model):
    PERIODS = [('day', 'Daily'), ('month', 'Monthly'), ('lifetime', 'Lifetime')]

    feature_code = models.SlugField(max_length=100)
    tier = models.CharField(max_length=20, choices=MembershipProfile.TIERS, default='free')
    period = models.CharField(max_length=20, choices=PERIODS, default='day')
    limit = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['feature_code', 'tier', 'period']
        constraints = [
            models.UniqueConstraint(fields=['feature_code', 'tier', 'period'], name='unique_usage_limit_per_feature_tier_period'),
        ]
        indexes = [
            models.Index(fields=['feature_code', 'tier', 'is_active']),
        ]

    def __str__(self):
        return f'{self.feature_code} / {self.tier} / {self.period}: {self.limit}'


class UsageRecord(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='usage_records')
    feature_code = models.SlugField(max_length=100)
    amount = models.PositiveIntegerField(default=1)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'feature_code', 'created_at']),
            models.Index(fields=['feature_code', 'created_at']),
        ]

    def __str__(self):
        return f'{self.user.email or self.user.username} / {self.feature_code} / {self.amount}'


class EmailVerificationRequest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='email_verification_requests')
    email = models.EmailField()
    token_hash = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'used_at', 'expires_at']),
            models.Index(fields=['token_hash']),
        ]

    def __str__(self):
        return f'{self.email} / {"used" if self.used_at else "pending"}'

    @property
    def is_valid(self):
        return not self.used_at and self.expires_at > timezone.now()


class PasswordHistory(models.Model):
    """A bounded, salted hash-only password history for an account."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_history')
    password_hash = models.CharField(max_length=256)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
        ]

    def __str__(self):
        return f'Password history for {self.user_id} at {self.created_at.isoformat()}'


class UserToolWorkspace(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tool_workspaces')
    tool_key = models.SlugField(max_length=80)
    data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'tool_key'], name='unique_user_tool_workspace'),
        ]
        indexes = [
            models.Index(fields=['user', 'tool_key']),
            models.Index(fields=['tool_key', 'updated_at']),
        ]
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.user.email or self.user.username} / {self.tool_key}'
