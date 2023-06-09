from typing import Optional

from django.http import JsonResponse

from django_glue.data_classes import GlueJsonResponseData
from django_glue.enums import GlueJsonResponseType, GlueJsonResponseStatus


def generate_json_200_response(
        message_title: str,
        message_body: str,
        data: Optional[dict] = None,
        optional_message_data: Optional[dict] = None,
) -> JsonResponse:

    return generate_json_200_response_data(
        message_title=message_title,
        message_body=message_body,
        data=data,
        optional_message_data=optional_message_data,
    ).to_django_json_response()


def generate_json_200_response_data(
        message_title: str,
        message_body: str,
        data: Optional[dict] = None,
        optional_message_data: Optional[dict] = None,
) -> GlueJsonResponseData:

    return GlueJsonResponseData(
        message_title=message_title,
        message_body=message_body,
        data=data,
        optional_message_data=optional_message_data,
        response_status=GlueJsonResponseStatus.SUCCESS,
        response_type=GlueJsonResponseType.SUCCESS,
    )


def generate_json_404_response() -> JsonResponse:
    return generate_json_404_response_data().to_django_json_response()


def generate_json_404_response_data() -> GlueJsonResponseData:
    return GlueJsonResponseData(
        message_title='Request not Found',
        message_body='The requested information, object or view you are looking for was not found.',
        response_status=GlueJsonResponseStatus.ERROR,
        response_type=GlueJsonResponseType.ERROR,
    )
