from django.urls import path

from test_project.lab import views

app_name = 'lab'

urlpatterns = [
    path('stress/', views.stress_view, name='stress'),
    path('flush-session/', views.flush_session_view, name='flush_session'),
]
