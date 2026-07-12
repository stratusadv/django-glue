from django.urls import path

from django_glue import constants
from django_glue.views.attribute_event_views import proxy_bound_attribute_event_view
from django_glue.views.view_views import glue_view_view

app_name = constants.BASE_URL_NAME

urlpatterns = [
    # These url path names are used in our middleware to avoid cleaning session data.
    path(
        route=f'{constants.BOUND_ATTRIBUTE_EVENT_URL_NAME}/<str:proxy_name>/<str:attribute_name>/',
        view=proxy_bound_attribute_event_view,
        name=constants.BOUND_ATTRIBUTE_EVENT_URL_NAME,
    ),
    path(
        route=f'{constants.GLUE_VIEW_URL_NAME}/',
        view=glue_view_view,
        name=constants.GLUE_VIEW_URL_NAME,
    ),
]
