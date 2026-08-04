from django.urls import path

from django_glue import constants
from django_glue.resolver.attribute_call.resolver import GlueAttributeCallResolver
from django_glue.resolver.view_fragment.resolver import GlueViewFragmentResolver

app_name = constants.BASE_URL_NAME

urlpatterns = [
    path(
        route=f'{constants.CALLABLE_ATTRIBUTE_URL_NAME}/<str:object_name>/<str:attribute_name>/',
        view=GlueAttributeCallResolver.as_view(),
        name=constants.CALLABLE_ATTRIBUTE_URL_NAME,
    ),
    path(
        route=f'{constants.GLUE_VIEW_URL_NAME}/',
        view=GlueViewFragmentResolver.as_view(),
        name=constants.GLUE_VIEW_URL_NAME,
    ),
]
