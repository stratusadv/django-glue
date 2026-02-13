from django.urls import path

from django_glue import views, constants

app_name = constants.BASE_URL_NAME

urlpatterns = [
    # These url path names are used in our middleware to avoid cleaning session data.
    path("", views.action_view, name=constants.ACTION_URL_NAME),
    path(f"{constants.KEEP_LIVE_URL_NAME}/", views.keep_live_view, name=constants.KEEP_LIVE_URL_NAME),
    path(f"{constants.SESSION_DATA_URL_NAME}/", views.session_data_view, name=constants.SESSION_DATA_URL_NAME),
]
