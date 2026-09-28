from django.urls import path

from test_project.lab.views import morph_views

app_name = 'morph'

urlpatterns = [
    path('', morph_views.morph_view, name='morph'),
    path('region/', morph_views.morph_region_view, name='morph_region'),
]
