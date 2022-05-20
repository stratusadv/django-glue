from django.urls import path

from django_glue import views

app_name = 'django_glue'

urlpatterns = [
    path("", views.joint_handler_view, name="joint_handler"),
]