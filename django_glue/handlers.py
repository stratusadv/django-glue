import logging, json

from django.contrib.contenttypes.models import ContentType
from django.forms import model_to_dict
from django.http import Http404

from django_glue.json import generate_json_response, generate_json_404_response
from django_glue.utils import process_and_save_field_value, process_and_save_form_values, get_glue_session, \
    decode_query_set_from_str, run_glue_method
from django_glue import settings


class GlueRequestHandler:
    def __init__(self, request):
        self.request = request

        self.is_model_object = False
        self.is_query_set = False

        if request.content_type == 'application/json':
            self.body_data = json.loads(request.body.decode('utf-8'))
        else:
            raise Http404

        self.unique_name = self.body_data['unique_name']

        self.glue_session = get_glue_session(request)
        self.context = self.glue_session['context']

        self.method = request.method

        if self.unique_name in self.context:
            self.model_class = ContentType.objects.get_by_natural_key(
                self.context[self.unique_name]['app_label'],
                self.context[self.unique_name]['model']).model_class()

            if self.context[self.unique_name]['connection'] == 'model_object':
                self.is_model_object = True
                self.model_object = self.model_class.objects.get(id=self.context[self.unique_name]['object_id'])

            elif self.context[self.unique_name]['connection'] == 'query_set':
                self.is_query_set = True
                self.query_set = self.glue_session['query_set']

    def process_response(self):
        if self.is_model_object:
            if self.method == 'DELETE':
                return self.delete_model_object_handler()
            elif self.method == 'GET':
                return self.get_model_object_handler()
            elif self.method == 'POST':
                return self.post_model_object_handler()
            elif self.method == 'PUT':
                return self.put_model_object_handler()
            else:
                return generate_json_404_response()
        elif self.is_query_set:
            if self.method == 'DELETE':
                return self.delete_query_set_handler()
            elif self.method == 'GET':
                return self.get_query_set_handler()
            elif self.method == 'POST':
                return self.post_query_set_handler()
            elif self.method == 'PUT':
                return self.put_query_set_handler()
            else:
                return generate_json_404_response()
        else:
            return generate_json_404_response()

    def delete_model_object_handler(self):
        if self.glue_session['access'] == 'delete':
            run_glue_method(self.request, self.model_object, 'django_glue_delete')

            if settings.DJANGO_GLUE_AUTO_DELETE:
                self.model_object.delete()

            return generate_json_response('200',
                                          'success',
                                          'Delete Object Success',
                                          'The object you are trying to delete was completed successful')
        else:
            return generate_json_404_response()

    def get_model_object_handler(self):
        run_glue_method(self.request, self.model_object, 'django_glue_view')

        return generate_json_response('200',
                                      'success',
                                      'Retrieve Object Data Success',
                                      'The object data you are trying to receive was successful',
                                      additional_data=model_to_dict(self.model_object))

    def post_model_object_handler(self):
        new_model_object = self.model_class()
        process_and_save_form_values(new_model_object, self.body_data['form_values'])

        run_glue_method(self.request, new_model_object, 'django_glue_create')

        return generate_json_response('200',
                                      'success',
                                      'Create Object Success',
                                      'The thing you tried to create was completely successful',
                                      additional_data=model_to_dict(new_model_object))

    def put_model_object_handler(self):
        if 'form_values' in self.body_data['data']:
            process_and_save_form_values(self.model_object, self.body_data['data']['form_values'])

        elif 'field_name' in self.body_data['data']:
            if self.body_data['data']['field_name'] in self.context[self.unique_name]['fields']:
                process_and_save_field_value(self.model_object, self.body_data['data']['field_name'],
                                             self.body_data['data']['value'])

        run_glue_method(self.request, self.model_object, 'django_glue_update')

        return generate_json_response('200',
                                      'success',
                                      'Update Object Successful',
                                      'The thing you tried to update was completely successful')

    def delete_query_set_handler(self):
        if id in self.body_data:
            working_query_set = decode_query_set_from_str(self.query_set[self.unique_name])
            try:
                model_object = working_query_set.get(id=self.body_data['id'])
            except self.model_class.DoesNotExist:
                return generate_json_404_response()

            run_glue_method(self.request, model_object, 'django_glue_delete')

            if settings.DJANGO_GLUE_AUTO_DELETE:
                model_object.delete()

            return generate_json_response('200',
                                          'success',
                                          'Delete Object in Query Set Success',
                                          'The thing you tried to delete was successful')
        else:
            return generate_json_404_response()

    def get_query_set_handler(self):
        if id in self.body_data:
            try:
                model_object = self.query_set.get(id=self.body_data['id'])
            except self.model_class.DoesNotExist:
                return generate_json_404_response()

            return generate_json_response('200',
                                          'success',
                                          'Retrieve Object Data in Query Set Success',
                                          'The object data in query set you are trying to receive was successful',
                                          additional_data=model_to_dict(model_object))
        else:
            working_query_set = decode_query_set_from_str(self.query_set[self.unique_name])
            model_object_list = dict()
            for model_object in working_query_set:
                model_object_list[model_object.id] = model_to_dict(model_object)

            return generate_json_response('200',
                                          'success', 'View Query Set Success',
                                          'The thing you tried to create was completely successful',
                                          additional_data=model_object_list)

    def post_query_set_handler(self):
        new_model_object = self.model_class()
        process_and_save_form_values(new_model_object, self.body_data['form_values'])

        run_glue_method(self.request, new_model_object, 'django_glue_create')

        return generate_json_response('200',
                                      'success',
                                      'Create Object in Queryset Success',
                                      'The thing you tried to create was completely successful',
                                      additional_data=model_to_dict(new_model_object))

    def put_query_set_handler(self):
        if id in self.body_data:
            try:
                model_object = self.query_set.get(id=self.body_data['id'])
            except self.model_class.DoesNotExist:
                return generate_json_404_response()

            if 'form_values' in self.body_data['data']:
                process_and_save_form_values(model_object, self.body_data['data']['form_values'])

            elif 'field_name' in self.body_data['data']:
                if self.body_data['data']['field_name'] in self.context[self.unique_name]['fields']:
                    process_and_save_field_value(model_object, self.body_data['data']['field_name'],
                                                 self.body_data['data']['value'])

            run_glue_method(self.request, self.model_object, 'django_glue_update')

            return generate_json_response('200',
                                          'success',
                                          'Update Successful',
                                          'The thing you tried to update was completely successful')
        else:
            return generate_json_404_response()
