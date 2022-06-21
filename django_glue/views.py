import json
import logging

from django.contrib.contenttypes.models import ContentType

from django_glue.utils import generate_json_response, generate_json_404_response


def glue_ajax_handler_view(request):
    body_data = json.loads(request.body.decode('utf-8'))

    rsc = request.session['django_glue']['context']
    rsq = request.session['django_glue']['query_sets']

    if 'method' in body_data:
        if body_data['unique_name'] in rsc:
            model_class = ContentType.objects.get_by_natural_key(rsc[body_data['unique_name']]['content_app_label'],
                                                                 rsc[body_data['unique_name']][
                                                                     'content_model']).model_class()
            model_object = model_class.objects.get(id=rsc[body_data['unique_name']]['object_id'])

            if body_data['method'] == 'update':

                if 'form_values' in body_data:
                    logging.warning(body_data['form_values'])
                    for key, val in body_data['form_values'].items():
                        model_object.__dict__[key] = val
                    model_object.save()
                elif 'field_name' in body_data:
                    if body_data['field_name'] in rsc[body_data['unique_name']]['fields']:
                        model_object.__dict__[body_data['field_name']] = body_data['value']
                        model_object.save()

                return generate_json_response('200', 'success', 'Update Successful',
                                              'The thing you tried to update was completely successful')

            elif body_data['method'] == 'create':
                new_model_object = model_class()
                for key, val in body_data['form_values'].items():
                    new_model_object.__dict__[key] = val
                new_model_object.save()

                return generate_json_response('200', 'success', 'Create Object Success',
                                              'The thing you tried to create was completely successful')

            else:
                return generate_json_404_response()

        else:
            return generate_json_404_response()

    else:
        return generate_json_404_response()
