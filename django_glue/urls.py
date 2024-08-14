from django.urls import path

from django_glue import views

app_name = 'django_glue'

urlpatterns = [
    # These url path names are used in our middleware to avoid cleaning session data.
    path("", views.glue_data_ajax_handler_view, name="django_glue_data_handler"),
    path("keep_live/", views.glue_keep_live_handler_view, name="django_glue_keep_live_handler"),
    path("session/", views.glue_session_data_view, name="django_glue_session_data"),
]
