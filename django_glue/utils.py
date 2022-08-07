import logging, pickle, base64


def camel_to_snake(string):
    return ''.join(['_' + c.lower() if c.isupper() else c for c in string]).lstrip('_')


def decode_query_set_from_str(query_set_string):
    query = pickle.loads(base64.b64decode(query_set_string))
    decoded_query_set = query.model.objects.all()
    decoded_query_set.query = query
    return decoded_query_set


def encode_query_set_to_str(query_set):
    return base64.b64encode(pickle.dumps(query_set.query)).decode()


def generate_field_dict(model_object, fields, exclude):
    fields_dict = dict()

    model = type(model_object)

    for field in model._meta.fields:
        try:
            if field.name not in exclude or exclude[0] == '__none__':
                if field.name in fields or fields[0] == '__all__':
                    if hasattr(field, 'get_internal_type'):
                        fields_dict[field.name] = {
                            'type': field.get_internal_type(),
                            'value': getattr(model_object, field.name)
                        }

        except:
            raise f'Invalid field or exclude for model type {model.name}'

    return fields_dict


def get_fields_from_model(model):
    return [field for field in model._meta.fields]