from django.urls import path, include

from test_project.developer.views import page_views

app_name = 'page'
urlpatterns = [
    path('session-data/', page_views.session_data_view, name='session_data'),
]