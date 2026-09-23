from django.urls import path

from django_glue import constants
from django_glue.resolver.attribute_call.resolver import GlueAttributeCallResolver

app_name = constants.BASE_URL_NAME

urlpatterns = [
    path(
        route=f'{constants.CALLABLE_ATTRIBUTE_URL_NAME}/',
        view=GlueAttributeCallResolver.as_view(),
        name=constants.CALLABLE_ATTRIBUTE_URL_NAME,
    ),
]
