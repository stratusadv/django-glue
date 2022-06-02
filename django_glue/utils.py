import logging
from uuid import uuid4

from django.contrib.contenttypes.models import ContentType


def add_object_glue(request, model_object, method, field_name=None, **kwargs):
    if 'django_glue' not in request.session:
        request.session['django_glue'] = dict()

    rs = request.session['django_glue']

    content_type = ContentType.objects.get_for_model(model_object)

    key = uuid4()

    rs[key] = {
        'model': 'test_model',
        'content_app_label': content_type.app_label,
        'content_model': content_type.model,
        'object_id': model_object.pk,
    }

    if type(field_name) is str:
        rs[key]['field_name'] = field_name

    elif field_name is None:
        pass

    else:
        raise TypeError('field argument must be a str object')


def camel_to_snake(string):
    return ''.join(['_' + c.lower() if c.isupper() else c for c in string]).lstrip('_')


def generate_glue_dict(request):
    glue_dict = {
        'fields': dict(),
        'objects': dict(),
    }

    for field_glue in models.FieldGlue.objects.all():
        try:
            glue_dict['fields'][camel_to_snake(field_glue.content_object.__class__.__name__)] = {
                'django_glue_key': field_glue.key,
                field_glue.field_name: field_glue.content_object.__dict__[field_glue.field_name],
            }
        except:
            logging.warning(f'Failed to load {field_glue = }')

    for object_glue in models.ObjectGlue.objects.all():
        try:
            glue_dict['objects'] = {
                camel_to_snake(object_glue.content_object.__class__.__name__): {
                    'django_glue_key': object_glue.key,
                    'data': object_glue.content_object,
                }
            }
        except:
            logging.warning(f'Failed to load {object_glue = }')

    return glue_dict


def convert_glue_dict_to_json(glue_dict):
    import json

    glue_json = {
        'fields': glue_dict['fields'],
        'objects': dict(),
    }

    exclude_field_type_list = ['AutoField', 'ManyToManyField']

    for key, val in glue_dict['objects'].items():
        glue_json['objects'][key] = {
            'django_glue_key': val['django_glue_key']
        }

        for field in val['data']._meta.get_fields():
            if hasattr(field, 'get_internal_type'):
                field_type = field.get_internal_type()
                if field_type not in exclude_field_type_list:
                    if field_type == 'DecimalField':
                        field_value = float(val['data'].__dict__[field.name])
                    else:
                        field_value = val['data'].__dict__[field.name]

                    glue_json['objects'][key][field.name] = field_value
                    # logging.warning(field.get_internal_type())

    return json.dumps(glue_json)
