import json

from django.contrib.contenttypes.models import ContentType

from django_glue.utils import generate_json_response


def glue_ajax_handler_view(request):
    body_data = json.loads(request.body.decode('utf-8'))

    if 'method' in body_data:
        rs = request.session['django_glue']

        if body_data['unique_name'] in rs:
            if body_data['field_name'] in rs[body_data['unique_name']]['fields']:

                model_class = ContentType.objects.get_by_natural_key(rs[body_data['unique_name']]['content_app_label'], rs[body_data['unique_name']]['content_model']).model_class()
                model_object = model_class.objects.get(id=rs[body_data['unique_name']]['object_id'])

                model_object.__dict__[body_data['field_name']] = body_data['value']
                model_object.save()

        return generate_json_response('200', 'success', 'Success message goes here and here and here!')

    else:
        return generate_json_response('404', 'error', 'Invalid method')
