from __future__ import annotations

import inspect
import json
import urllib.parse
from typing import Optional, Callable, Union

from django.core import serializers
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Model
from django.http import HttpRequest


def check_valid_method_kwargs(method: Callable, kwargs: Optional[dict]):
    for kwarg in kwargs:
        if kwarg not in inspect.signature(method).parameters.keys():
            return False
    return True


def encode_unique_name(request: HttpRequest, unique_name: str) -> str:
    if 'glue_encode_path' in request.GET:
        encode_path = request.GET['glue_encode_path']
    else:
        encode_path = request.path_info

    return urllib.parse.quote(f'{unique_name}|{encode_path}', safe='')


def serialize_to_json(data: Union[dict, tuple, list, str, int, float, ]) -> str:
    return json.dumps(data, cls=DjangoJSONEncoder)


def type_set_method_kwargs(method: Callable, kwargs: Optional[dict]) -> dict:
    type_set_kwargs = {}

    # This is a dict consisting of all kwargs and there type annotations (If they have type annotations)
    annotations = inspect.getfullargspec(method).annotations

    for kwarg in kwargs:
        if kwarg in annotations:
            # Converts the kwarg to match the type specified in on the methods kwargs
            type_set_kwargs[kwarg] = inspect.getfullargspec(method).annotations[kwarg](kwargs[kwarg])
        else:
            # If there is not a type annotation, the value remains the same
            type_set_kwargs[kwarg] = kwargs[kwarg]

    return type_set_kwargs


def camel_to_snake(string: str) -> str:
    return ''.join(['_' + c.lower() if c.isupper() else c for c in string]).lstrip('_')


def serialize_object_to_json(model_object: Model) -> str:
    return serializers.serialize('json', [model_object, ])
