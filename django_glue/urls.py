from django.urls import path

from django_glue import views, constants

app_name = constants.BASE_URL_NAME

urlpatterns = [
    # These url path names are used in our middleware to avoid cleaning session data.
    path(
        f'{constants.ACTION_URL_NAME}/<str:unique_name>/<str:action>/',
        views.action_view,
        name=constants.ACTION_URL_NAME,
    ),
    path(
        f'{constants.KEEP_LIVE_URL_NAME}/', views.keep_live_view, name=constants.KEEP_LIVE_URL_NAME
    ),
    path(
        f'{constants.SESSION_DATA_URL_PATH_NAME}/',
        views.session_data_view,
        name=constants.SESSION_DATA_URL_PATH_NAME,
    ),
    path(
        f'{constants.GLUE_VIEW_URL_NAME}/', views.glue_view_view, name=constants.GLUE_VIEW_URL_NAME
    ),
]
