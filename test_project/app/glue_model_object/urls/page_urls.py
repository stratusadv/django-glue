from django.urls import path

from test_project.app.glue_model_object.views import page_views

app_name = 'page'

urlpatterns = [
    path('list',
         page_views.list_view,
         name='list'),
]
