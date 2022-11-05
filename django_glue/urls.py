from django.urls import path

from django_glue import views

app_name = 'django_glue'

urlpatterns = [
    path("", views.glue_data_ajax_handler_view, name="django_glue_data_handler"),
    path("keep_live/", views.glue_keep_live_handler_view, name="django_glue_keep_live_handler"),
]