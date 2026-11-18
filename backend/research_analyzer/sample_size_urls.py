from django.urls import path

from . import sample_size_views as views


urlpatterns = [
    path('designs/', views.designs, name='api_sample_size_designs'),
    path('calculate/', views.calculate, name='api_sample_size_calculate'),
    path('docx/', views.export_docx, name='api_sample_size_docx'),
]
