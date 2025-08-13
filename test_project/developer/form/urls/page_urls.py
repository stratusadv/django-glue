from django.urls import path, include

from test_project.developer.form.views import page_views

app_name = 'page'
urlpatterns = [
    path('dashboard/', page_views.dashboard_view, name='dashboard'),
]