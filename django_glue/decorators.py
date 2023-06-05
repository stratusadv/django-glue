from functools import wraps
from inspect import signature

def glue_method(function):
    return glue_function(function, _type_name='Method')


def glue_function(function, _type_name='Function'):
    function_signature = signature(function)

    if 'request' not in function_signature.parameters:
        raise f'{_type_name} "{function.__name__}" does not take "request" as an argument'
    @wraps(function)
    def wrapper(*args, **kwargs):
        return function(*args, **kwargs)

    wrapper._is_glue_function = True

    return wrapper