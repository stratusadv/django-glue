from django_glue import models


def add_or_update_joint(model_object, method, field_name=None, **kwargs):
    arguments = {
        'content_object': model_object,
        'method': method,
    }

    if type(field_name) is str:
        field_joint = models.FieldJoint(
            **arguments,
            field_name=field_name
        )

        field_joint.save()

    elif field_name is None:
        model_object_joint = models.ModelObjectJoint(
            **arguments,
        )

        model_object_joint.save()

    else:
        raise TypeError('field argument must be a str object')


def add_joint(model_object,  method, field_name=None, **kwargs):
    add_or_update_joint(model_object, method, field_name)


