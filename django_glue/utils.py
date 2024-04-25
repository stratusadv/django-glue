import inspect
import urllib.parse
from typing import Optional, Callable


def check_valid_method_kwargs(method: Callable, kwargs: Optional[dict]):
    for kwarg in kwargs:
        if kwarg not in inspect.signature(method).parameters.keys():
            return False
    return True


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


def encode_unique_name(request, unique_name):
    if 'glue_encode_path' in request.GET:
        encode_path = request.GET['glue_encode_path']
    else:
        encode_path = request.path_info

    return urllib.parse.quote(f'{unique_name}|{encode_path}', safe='')
