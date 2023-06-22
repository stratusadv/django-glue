from dataclasses import fields

from django.core import serializers


def camel_to_snake(string):
    return ''.join(['_' + c.lower() if c.isupper() else c for c in string]).lstrip('_')


def remove_none_value_field_from_data_class_object(obj):
    for field in fields(obj):
        if getattr(obj, field.name) is None:
            delattr(obj, field.name)


def serialize_object_to_json(model_object):
    return serializers.serialize('json', [model_object, ])
