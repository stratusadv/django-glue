from django.urls import path

from test_project.glue.views import page_views

app_name = 'page'
urlpatterns = [
    path('', page_views.main_page_view, name='main'),
    path('session-data/', page_views.session_data_view, name='session_data'),
]