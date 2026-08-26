from django.urls import path

from test_project.lab.views import performance_views, volume_views

app_name = 'performance'

urlpatterns = [
    path('speed/', performance_views.speed_view, name='speed'),
    path('stress/', performance_views.stress_view, name='stress'),
    path('flush-session/', performance_views.flush_session_view, name='flush_session'),
    path('volume/', volume_views.volume_view, name='volume'),
    path('volume/seed/', volume_views.seed_specimens_view, name='volume_seed'),
    path('volume/clear/', volume_views.clear_specimens_view, name='volume_clear'),
]
