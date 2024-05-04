from abc import ABC, abstractmethod
from typing import Type

from django.db.models import Field
from django_glue.form import html_attrs


class GlueAttrFactory(ABC):
    glue_attr: Type[html_attrs.GlueFieldAttrs] = None

    def __init__(self, model_field: Field):
        self.model_field = model_field

    def factory_method(self) -> html_attrs.GlueFieldAttrs:
        kwargs = self.base_kwargs() | self.field_kwargs()
        print(kwargs)
        return self.glue_attr(**kwargs)

    def base_kwargs(self) -> dict:
        return {
            'name': self.model_field.name,
            'required': self.model_field.blank,
            'hidden': self.model_field.hidden,
            'disabled': not self.model_field.editable,
            # 'help_text': self.model_field.help_text,  # Todo: Was raising an error with proxy field.
            'choices': self.model_field.choices
        }

    @abstractmethod
    def field_kwargs(self) -> dict:
        pass


class GlueCharAttrFactory(GlueAttrFactory):
    glue_attr = html_attrs.GlueCharFieldAttr

    def field_kwargs(self) -> dict:
        return {
            'max_length': self.model_field.max_length,
        }
