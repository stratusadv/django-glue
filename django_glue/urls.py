from django.urls import path

from django_glue import constants
from django_glue.views.action_views import action_view
from django_glue.views.keep_live_views import keep_live_view
from django_glue.views.session_data_views import session_data_view
from django_glue.views.view_views import glue_view_view

app_name = constants.BASE_URL_NAME

urlpatterns = [
    # These url path names are used in our middleware to avoid cleaning session data.
    path(
        route=f'{constants.ACTION_URL_NAME}/<str:unique_name>/<str:action>/',
        view=action_view,
        name=constants.ACTION_URL_NAME,
    ),
    path(
        route=f'{constants.KEEP_LIVE_URL_NAME}/',
        view=keep_live_view,
        name=constants.KEEP_LIVE_URL_NAME,
    ),
    path(
        route=f'{constants.SESSION_DATA_URL_NAME}/',
        view=session_data_view,
        name=constants.SESSION_DATA_URL_NAME,
    ),
    path(
        route=f'{constants.GLUE_VIEW_URL_NAME}/',
        view=glue_view_view,
        name=constants.GLUE_VIEW_URL_NAME,
    ),
]
