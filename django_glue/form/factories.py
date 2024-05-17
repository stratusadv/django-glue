from abc import ABC, abstractmethod
from typing import Type

from django.db.models import Field
from django_glue.form import html_attrs


class GlueAttrFactory(ABC):
    glue_attr: Type[html_attrs.GlueFieldAttrs] = None

    def __init__(self, model_field: Field):
        self.model_field = model_field

    def factory_method(self) -> dict:
        return self.base_attrs() | self.field_attrs()

    def base_attrs(self) -> dict:
        print(self.model_field.name)
        return {
            'name': self.model_field.name,
            'id': f'id_{self.model_field.name}',
            'label': ' '.join(word.capitalize() for word in self.model_field.name.split('_')),
            'required': self.model_field.blank,
            'hidden': self.model_field.hidden,
            'disabled': not self.model_field.editable,
            'choices': self.model_field.choices
            # 'help_text': self.model_field.help_text,  # Todo: Was raising an error with proxy field.
        }

    @abstractmethod
    def field_attrs(self) -> dict:
        pass


class GlueCharAttrFactory(GlueAttrFactory):
    glue_attr = html_attrs.GlueCharFieldAttr

    def field_attrs(self) -> dict:
        return {
            'maxlength': self.model_field.max_length,
            'type': 'text'
        }
