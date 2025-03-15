from django.urls import path

from django_glue import views_ajax, constants

app_name = constants.URL_APP_NAME

urlpatterns = [
    # These url path names are used in our middleware to avoid cleaning session data.
    path("", views_ajax.handler_ajax_view, name=constants.HANDLER_URL_NAME),
    path("keep_live/", views_ajax.keep_live_handler_ajax_view, name=constants.KEEP_LIVE_HANDLER_URL_NAME),
    path("session/", views_ajax.session_data_ajax_view, name=constants.SESSION_DATA_URL_NAME),
]
