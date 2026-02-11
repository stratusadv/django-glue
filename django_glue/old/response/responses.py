from typing import Optional

from django.http import JsonResponse

from django_glue.response.data import BaseJsonData, JsonResponseData
from django_glue.response.enums import JsonResponseStatus, JsonResponseType


def generate_json_200_response_data(
        message_title: str,
        message_body: str,
        data: Optional[BaseJsonData] = None,
        optional_message_data: Optional[dict] = None,
) -> JsonResponseData:

    return JsonResponseData(
        message_title=message_title,
        message_body=message_body,
        data=data,
        optional_message_data=optional_message_data,
        response_status=JsonResponseStatus.SUCCESS,
        response_type=JsonResponseType.SUCCESS,
    )


def generate_json_404_response(
        message_title: str = 'Request not Found',
        message_body: str = 'The requested information, object or view you are looking for was not found.',
) -> JsonResponse:

    return generate_json_404_response_data(
        message_title,
        message_body,
    ).to_django_json_response()


def generate_json_404_response_data(
        message_title: str = 'Request not Found',
        message_body: str = 'The requested information, object or view you are looking for was not found.',
) -> JsonResponseData:

    return JsonResponseData(
        message_title=message_title,
        message_body=message_body,
        response_status=JsonResponseStatus.ERROR,
        response_type=JsonResponseType.ERROR,
    )
