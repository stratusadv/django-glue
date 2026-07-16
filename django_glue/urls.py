from django.urls import path

from django_glue import constants
from django_glue.glue.views import glue_attribute_call_view
from django_glue.views.view_views import glue_view_view

app_name = constants.BASE_URL_NAME

urlpatterns = [
    path(
        route=f'{constants.CALLABLE_ATTRIBUTE_URL_NAME}/<str:object_name>/<str:attribute_name>/',
        view=glue_attribute_call_view,
        name=constants.CALLABLE_ATTRIBUTE_URL_NAME,
    ),
    path(
        route=f'{constants.GLUE_VIEW_URL_NAME}/',
        view=glue_view_view,
        name=constants.GLUE_VIEW_URL_NAME,
    ),
]
