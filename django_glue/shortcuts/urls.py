from django.urls import path, include

from django_glue import constants


def django_glue_urls() -> list:
    return [
        path(
            f'{constants.BASE_URL_NAME}/',
            include('django_glue.urls', namespace=constants.BASE_URL_NAME),
        )
    ]
