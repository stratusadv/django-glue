from django.urls import path

from test_project.glue.form.fields.views import page_views

app_name = 'page'
urlpatterns = [
    path('<int:pk>/detail/', page_views.detail_view, name='detail'),
    path('list/', page_views.list_view, name='list'),
]