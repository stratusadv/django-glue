import json
import logging

from django.http import JsonResponse


def glue_ajax_handler_view(request):
    logging.warning('Glue Handler Start')

    body_data = json.loads(request.body.decode('utf-8'))

    logging.warning(f'{body_data = }')

    json_response = {
        'status': True,
    }

    return JsonResponse(json_response)
