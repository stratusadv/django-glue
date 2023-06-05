from django.http import JsonResponse

JSON_RESPONSE_TYPES = (
    'success',
    'info',
    'warning',
    'error',
    'debug',
)


def generate_json_response(
        message_title,
        message_body,
        message_dict=None,
        response_status='200',
        response_type='success',
        additional_data=None
):
    if message_dict is None:
        message_dict = dict()

    if response_type not in JSON_RESPONSE_TYPES:
        raise ValueError(f'response_type "{response_type}" is not a valid, choices are {JSON_RESPONSE_TYPES}')

    return JsonResponse({
        'type': response_type,
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
