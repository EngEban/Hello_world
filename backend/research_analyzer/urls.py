from django.urls import path

from . import views


urlpatterns = [
    path('upload/', views.upload_file, name='api_research_analyzer_upload'),
    path('variables/', views.update_variables, name='api_research_analyzer_variables'),
    path('prepare/', views.prepare_data, name='api_research_analyzer_prepare'),
    path('analyze/', views.run_analysis, name='api_research_analyzer_analyze'),
    path('analysis-plan/', views.analysis_plan, name='api_research_analyzer_analysis_plan'),
    path('report/generate/', views.generate_master_analysis, name='api_research_analyzer_generate_report'),
    path('report/', views.master_report, name='api_research_analyzer_report'),
    path('session/<str:session_id>/clear/', views.clear_session, name='api_research_analyzer_clear_session'),
    path('methods/', views.method_catalog, name='api_research_analyzer_methods'),
    path('recommend/', views.recommend_method, name='api_research_analyzer_recommend'),
    path('levels/', views.variable_levels, name='api_research_analyzer_levels'),
    path('report/docx/', views.export_docx, name='api_research_analyzer_export_docx'),
]
