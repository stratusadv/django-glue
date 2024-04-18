from django.db.models import Model

from django_glue.form.fields import FormField


def form_field_from_django_model_field(model_field, model_object: Model) -> FormField:
    # Index the type of field depending on a map
    # Get the field object
    # Process the field object from the model field
    pass