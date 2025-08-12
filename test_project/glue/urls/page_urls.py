from django.urls import path

from test_project.glue.views import page_views

app_name = 'page'
urlpatterns = [
    path('session-data/', page_views, name='session_data'),
]