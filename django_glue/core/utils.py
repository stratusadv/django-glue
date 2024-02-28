from dataclasses import fields

from django.core import serializers


def camel_to_snake(string):
    return ''.join(['_' + c.lower() if c.isupper() else c for c in string]).lstrip('_')


def serialize_object_to_json(model_object):
    return serializers.serialize('json', [model_object, ])
