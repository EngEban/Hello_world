from django.urls import path

from . import views


urlpatterns = [
    path('', views.usage_overview_api, name='usage_overview'),
    path('admin/policies/', views.admin_policies_api, name='usage_admin_policies'),
    path('admin/policies/<slug:feature_code>/save/', views.admin_save_policy_api, name='usage_admin_save_policy'),
    path('<slug:feature_code>/', views.feature_usage_api, name='usage_feature'),
    path('<slug:feature_code>/consume/', views.consume_usage_api, name='usage_consume'),
]
