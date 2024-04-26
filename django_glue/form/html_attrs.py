from abc import ABC
from typing import Any, Union, Optional

from django.db.models import Field

from django_glue.form.enums import FieldType

"""
    Model attribute names match model field names to dynamically create GlueFieldAttrs instances.
    html_attrs key represents name of html attribute.
    
"""


class GlueFieldAttrs(ABC):
    type = None

    def __init__(
            self,
            name: str,
            requried: bool = False,
            hidden: bool = False,
            help_text: str = '',
            disabled: bool = True,
            choices: Union[list, tuple, None] = None
    ):
        if self.type is None:
            raise Exception(f"Field {self.__class__.__name__} has no type")

        self.requried = requried  # Matches django model fields
        self.disabled = disabled
        self.hidden = hidden
        self.name = name
        self.help_text = help_text
        self.choices = choices

        self.html_attrs = self._base_html_attrs() | self.extra_html_attrs()

    def to_dict(self):
        pass

    @classmethod
    def kwargs_from_model_field(cls, model_field: Field) -> dict:
        return {
            'name': model_field.name,
            'requried': model_field.blank,
            'hidden': model_field.hidden,
            'disabled': not model_field.editable,
            'help_text': model_field.help_text,
            'choices': model_field.choices
        }

    def _base_html_attrs(self) -> dict:
        return {
            'required': self.requried,
            'hidden': self.hidden,
            'label': ' '.join(word.capitalize() for word in self.name.split('_')),
            'id': f'id_{self.name}',
            'help_text': self.help_text,
            'disabled': self.disabled,
            'choices': self.choices
        }

    def extra_html_attrs(self) -> dict:
        return {}


class GlueBooleanField(GlueFieldAttrs):
    type = FieldType.BOOLEAN


class GlueCharField(GlueFieldAttrs):
    type = FieldType.CHAR

    def __init__(self, max_length: int, **kwargs):
        self.max_length = max_length
        super().__init__(**kwargs)

    @classmethod
    def kwargs_from_model_field(cls, model_field: Field) -> dict:
        kwargs = super().kwargs_from_model_field(model_field)
        kwargs['max_length'] = model_field.max_length
        return kwargs

    def extra_html_attrs(self) -> dict:
        return {
            'maxlength': self.max_length,
            'type': 'text'
        }


class GlueDateField(GlueFieldAttrs):
    type = FieldType.DATE

    def extra_html_attrs(self) -> dict:
        return {'input_type': 'date'}


class GlueDateTimeField(GlueFieldAttrs):
    type = FieldType.DATETIME

    def extra_html_attrs(self) -> dict:
        return {'input_type': 'datetime-local'}


class GlueDecimalField(GlueFieldAttrs):
    type = FieldType.DECIMAL

    def __init__(self, max_digits: int, decimal_places: int, **kwargs):
        super().__init__(**kwargs)
        self.max_digits = max_digits
        self.decimal_places = decimal_places

    def extra_html_attrs(self) -> dict:
        return {
            'max_digits': self.max_digits,
            'decimal_places': self.decimal_places,
            'input_type': 'number'
        }


class GlueEmailField(GlueFieldAttrs):
    type = FieldType.EMAIL

    def extra_html_attrs(self) -> dict:
        return {'input_type': 'email'}


class GlueFloatField(GlueFieldAttrs):
    type = FieldType.FLOAT

    def extra_html_attrs(self) -> dict:
        return {'input_type': 'number'}


class GlueIntegerField(GlueFieldAttrs):
    type = FieldType.INTEGER

    def extra_html_attrs(self) -> dict:
        return {'input_type': 'number'}


class GlueTextField(GlueFieldAttrs):
    type = FieldType.TEXT

    def extra_html_attrs(self) -> dict:
        return {
            'rows': 5,
            'cols': 40,
            'input_type': 'text'
        }
