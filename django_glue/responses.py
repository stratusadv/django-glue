from typing import Optional

from django.http import JsonResponse

from django_glue.enums import GlueJsonResponseType

def generate_json_response(
        message_title: str,
        message_body: str,
        message_dict: Optional[dict] = None,
        response_status: str = '200',
        response_type: str = 'success',
        additional_data = None
):

    if message_dict is None:
        message_dict = dict()

    return JsonResponse({
        'type': GlueJsonResponseType(response_type).value,
        'message_title': message_title,
        'message_body': message_body,
        'message_dict': message_dict,
        'data': additional_data
    }, status=response_status)


def generate_json_404_response():
    return generate_json_response(
        message_title='Request not Found',
        message_body='The requested information, object or view you are looking for was not found.',
        response_status='404',
        response_type='error',
    )
