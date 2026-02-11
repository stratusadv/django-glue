from django.urls import path

from django_glue import views_ajax, constants

app_name = constants.BASE_URL_NAME

urlpatterns = [
    # These url path names are used in our middleware to avoid cleaning session data.
    path("", views_ajax.handler_ajax_view, name=constants.ACTION_URL_NAME),
    path("keep_live/", views_ajax.keep_live_view, name=constants.KEEP_LIVE_HANDLER_URL_NAME),
    path("session/", views_ajax.session_data_view, name=constants.SESSION_DATA_URL_NAME),
]
