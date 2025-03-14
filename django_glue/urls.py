from django.urls import path

from django_glue import views_ajax

app_name = 'django_glue'

urlpatterns = [
    # These url path names are used in our middleware to avoid cleaning session data.
    path("", views_ajax.handler_ajax_view, name="django_glue_handler"),
    path("keep_live/", views_ajax.keep_live_handler_ajax_view, name="django_glue_keep_live_handler"),
    path("session/", views_ajax.session_data_ajax_view, name="django_glue_session_data"),
]
