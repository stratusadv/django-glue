import json
import logging

from django.http import JsonResponse

from django_glue import models


def glue_ajax_handler_view(request):
    logging.warning('Glue Handler Start')

    body_data = json.loads(request.body.decode('utf-8'))

    logging.warning(f'{body_data = }')

    if body_data['type'] == 'fields':
        logging.warning('Updating Field Glue Object')
        model_object = models.FieldGlue.objects.get(key=body_data['key'])
        model_object.content_object.__dict__[model_object.field_name] = body_data['value']
        model_object.content_object.save()
    if body_data['type'] == 'objects':
        logging.warning('Updating Object Glue Object')
        model_object = models.ObjectGlue.objects.get(key=body_data['key'])
        model_object.content_object.__dict__[body_data['field']] = body_data['value']
        model_object.content_object.save()

    json_response = {
        'status': True,
    }

    logging.warning(request.session['key_dict'])

    from django.contrib.contenttypes.models import ContentType

    rs = request.session['key_dict']['super_secret_key']

    model_class = ContentType.objects.get_by_natural_key(rs['content_app_label'], rs['content_model']).model_class()

    model_object = model_class.objects.get(id=rs['object_id'])

    logging.warning(f'{model_object = }')

    return JsonResponse(json_response)
