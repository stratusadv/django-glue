from abc import ABC, abstractmethod
from dataclasses import dataclass

from django.db.models import Model, Field
from django_glue.form import fields
from django_glue.form.maps import FIELD_TYPE_TO_GLUE_FIELD


def glue_field_from_model_field(model: Model, model_field: Field) -> fields.GlueField:
        # Dynamically builds the GlueField class from the model and model_field
        glue_field_class = FIELD_TYPE_TO_GLUE_FIELD[model.__class__.__name__]

        kwargs = {}
        for attr_name in dir(glue_field_class):

            attr_value = getattr(model_field, attr_name)

            if attr_value is not None:
                kwargs[attr_name] = attr_value

        return glue_field_class(**kwargs)





@dataclass
class GlueFieldFactory(ABC):
    model_object: Model
    model_field: Field

    @abstractmethod
    def factory_method(self):
        pass


@dataclass
class GlueCharFieldFactory(GlueFieldFactory):

    def factory_method(self):
        pass
