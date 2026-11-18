from django.urls import path
from dashboard import public_forms
from dashboard.api import team_page

from . import api_views

urlpatterns = [
    path('home/', api_views.home_api, name='api_home'),
    path('search/', api_views.unified_search_api, name='api_unified_search'),
    path('posts/', api_views.posts_api, name='api_posts'),
    path('posts/<slug:slug>/', api_views.post_detail_api, name='api_post_detail'),
    path('pages/<slug:slug>/', api_views.page_detail_api, name='api_page_detail'),
    path('categories/', api_views.categories_api, name='api_categories'),
    path('authors/', api_views.authors_api, name='api_authors'),
    path('authors/<slug:slug>/', api_views.author_detail_api, name='api_author_detail'),
    path('opportunities/', api_views.opportunities_api, name='api_opportunities'),
    path('join-team/', api_views.join_team_entries_api, name='api_join_team_entries'),
    path('faq/', api_views.faq_api, name='api_faq'),
    path('team/', team_page.public_team_page_api, name='api_team_page'),
    path('site-settings/', api_views.site_settings_api, name='api_site_settings'),
    path('contact/', api_views.contact_submit_api, name='api_contact_submit'),
    path('applications/', public_forms.submit_application_api, name='api_application_submit'),
    path('service-requests/', public_forms.submit_service_request_api, name='api_service_request_submit'),
    path('newsletter/subscribe/', api_views.newsletter_subscribe_api, name='api_newsletter_subscribe'),
    path('newsletter/confirm/', api_views.newsletter_confirm_api, name='api_newsletter_confirm'),
    path('references/fetch/', api_views.fetch_reference_api, name='api_fetch_reference'),
]
