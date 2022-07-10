import json
import logging

from django.contrib.contenttypes.models import ContentType

from django_glue.utils import generate_json_response, generate_json_404_response, process_and_save_form_values, process_and_save_field_value, decode_query_set_from_str
from django_glue import settings


def glue_ajax_handler_view(request):
    body_data = json.loads(request.body.decode('utf-8'))
    bd = body_data

    rsc = request.session[settings.DJANGO_GLUE_SESSION_NAME]['context']
    rsq = request.session[settings.DJANGO_GLUE_SESSION_NAME]['query_set']

    if 'method' in bd:
        if bd['unique_name'] in rsc:
            if rsc[bd['unique_name']]['connection'] == 'model_object':
                model_class = ContentType.objects.get_by_natural_key(
                    rsc[bd['unique_name']]['app_label'],
                    rsc[bd['unique_name']]['model']).model_class()

                model_object = model_class.objects.get(id=rsc[bd['unique_name']]['object_id'])

                if bd['method'] == 'update':

                    if 'form_values' in bd:
                        process_and_save_form_values(model_object, bd['form_values'])

                    elif 'field_name' in bd:
                        if bd['field_name'] in rsc[bd['unique_name']]['fields']:
                            process_and_save_field_value(model_object, bd['field_name'], bd['value'])

                    return generate_json_response('200', 'success', 'Update Successful',
                                                  'The thing you tried to update was completely successful')

                elif bd['method'] == 'create':
                    new_model_object = model_class()
                    process_and_save_form_values(new_model_object, bd['form_values'])

                    return generate_json_response('200', 'success', 'Create Object Success',
                                                  'The thing you tried to create was completely successful')

            if rsc[bd['unique_name']]['connection'] == 'query_set':
                if bd['method'] == 'read':
                    from django.forms.models import model_to_dict
                    working_query_set = decode_query_set_from_str(rsq[bd['unique_name']])
                    model_object_list = dict()
                    for model_object in working_query_set:
                        model_object_list[model_object.id] = model_to_dict(model_object)

                    return generate_json_response('200', 'success', 'View Query Set Success',
                                                  'The thing you tried to create was completely successful', additional_data=model_object_list)

    logging.warning('404 Error Generated By Code')
    return generate_json_404_response()
