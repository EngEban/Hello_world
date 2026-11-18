from django.urls import path

from . import api_views


urlpatterns = [
    path('csrf/', api_views.csrf_api, name='api_accounts_csrf'),
    path('config/', api_views.config_api, name='api_accounts_config'),
    path('register/', api_views.register_api, name='api_accounts_register'),
    path('register/confirm/', api_views.confirm_registration_api, name='api_accounts_register_confirm'),
    path('register/resend/', api_views.resend_confirmation_api, name='api_accounts_register_resend'),
    path('login/', api_views.login_api, name='api_accounts_login'),
    path('google/', api_views.google_login_api, name='api_accounts_google'),
    path('google/link/', api_views.google_link_api, name='api_accounts_google_link'),
    path('logout/', api_views.logout_api, name='api_accounts_logout'),
    path('me/', api_views.me_api, name='api_accounts_me'),
    path('tool-workspaces/<slug:tool_key>/', api_views.tool_workspace_api, name='api_accounts_tool_workspace'),
    path('tool-usage/<slug:tool_key>/', api_views.tool_usage_api, name='api_accounts_tool_usage'),
    path('profile/', api_views.update_profile_api, name='api_accounts_profile'),
    path('password/', api_views.change_password_api, name='api_accounts_password'),
    path('password-reset/', api_views.request_password_reset_api, name='api_accounts_password_reset'),
    path('password-reset/confirm/', api_views.confirm_password_reset_api, name='api_accounts_password_reset_confirm'),
    path('email-verification/', api_views.request_email_verification_api, name='api_accounts_email_verification'),
    path('email-verification/confirm/', api_views.confirm_email_verification_api, name='api_accounts_email_verification_confirm'),
    path('email/', api_views.request_email_change_api, name='api_accounts_email_change'),
    path('email/confirm/', api_views.confirm_email_change_api, name='api_accounts_email_change_confirm'),
    path('export/', api_views.export_account_api, name='api_accounts_export'),
    path('delete/', api_views.delete_account_api, name='api_accounts_delete'),
    path('billing/checkout/', api_views.billing_checkout_api, name='api_accounts_billing_checkout'),
    path('billing/portal/', api_views.billing_portal_api, name='api_accounts_billing_portal'),
    path('billing/cancel/', api_views.billing_cancel_api, name='api_accounts_billing_cancel'),
    path('billing/webhook/', api_views.stripe_webhook_api, name='api_accounts_stripe_webhook'),
    path('notifications/', api_views.notifications_api, name='api_accounts_notifications'),
    path('notifications/<int:pk>/read/', api_views.notification_read_api, name='api_accounts_notification_read'),
]
