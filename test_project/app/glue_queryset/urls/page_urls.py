from django.urls import path

from test_project.app.glue_queryset.views import page_views

app_name = 'page'

urlpatterns = [
    path('list',
         page_views.dashboard_view,
         name='dashboard'),
]
