from django.urls import path

from test_project.lab.views import performance_views

app_name = 'performance'

urlpatterns = [
    path('stress/', performance_views.stress_view, name='stress'),
    path('flush-session/', performance_views.flush_session_view, name='flush_session'),
]
