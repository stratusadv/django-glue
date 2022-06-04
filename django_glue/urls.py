from django.urls import path

from django_glue import views

app_name = 'django_glue'

urlpatterns = [
    path("", views.glue_ajax_handler_view, name="django_glue_handler"),
]