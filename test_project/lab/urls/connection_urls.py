from __future__ import annotations

from django.urls import path

from test_project.lab.views import connection_views

app_name = 'connection'

urlpatterns = [
    path('', connection_views.connection_view, name='connection'),
    path('logout/', connection_views.logout_user_view, name='logout'),
    path('delete-session/', connection_views.delete_session, name='delete_session'),
    path('remove-proxy/', connection_views.remove_unique_name, name='remove_proxy'),
    path('expire/', connection_views.expire_session, name='expire'),
]
