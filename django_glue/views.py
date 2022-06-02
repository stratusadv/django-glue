import json
import logging

from django.http import JsonResponse
from django.contrib.contenttypes.models import ContentType


def glue_ajax_handler_view(request):
    logging.warning('Glue Handler Start')

    body_data = json.loads(request.body.decode('utf-8'))

    logging.warning(f'{body_data = }')

    rs = request.session['django_glue']

    logging.warning(f'{ rs = }')

    model_class = ContentType.objects.get_by_natural_key(rs['content_app_label'], rs['content_model']).model_class()
    model_object = model_class.objects.get(id=rs['object_id'])

    logging.warning(f'{model_object = }')

    if body_data['type'] == 'fields':
        logging.warning('Updating Field Glue Object')
        model_object.content_object.__dict__[model_object.field_name] = body_data['value']
        model_object.content_object.save()
    if body_data['type'] == 'objects':
        logging.warning('Updating Object Glue Object')
        model_object.content_object.__dict__[body_data['field']] = body_data['value']
        model_object.content_object.save()

    json_response = {
        'status': True,
    }


    return JsonResponse(json_response)
