from abc import ABC, abstractmethod
from typing import Any, Union

from django_glue.form.enums import FieldType

"""
    Model attribute names match model field names to dynamically create GlueField instances.
    html_attrs key represents name of html attribute.
    
"""


class GlueField(ABC):
    type = None

    def __init__(
            self,
            value: Any,
            required: bool,
            hidden: bool,
            label: str,
            help_text: str,
            choices: Union[list, tuple, None]
    ):
        if self.type is None:
            raise Exception(f"Field {self.__class__.__name__} has no type")

        self.value = value
        self.required = required
        self.hidden = hidden
        self.label = label
        self.help_text = help_text
        self.choices = choices

        self.html_attrs = self._base_html_attrs() | self.extra_html_attrs()

    def to_dict(self):
        pass

    def _base_html_attrs(self) -> dict:
        return {
            'value': self.value,
            'required': self.required,
            'hidden': self.hidden,
            'label': self.label,
            'help_text': self.help_text,
            'choices': self.choices
        }

    def extra_html_attrs(self) -> dict:
        return {}


class GlueBooleanField(GlueField):
    type = FieldType.BOOLEAN


class GlueCharField(GlueField):
    type = FieldType.CHAR

    def __init__(self, max_length: int, **kwargs):
        super().__init__(**kwargs)
        self.max_length = max_length

    def extra_html_attrs(self) -> dict:
        return {
            'max_length': self.max_length,
            'input_type': 'text'
        }


class GlueDateField(GlueField):
    type = FieldType.DATE

    def extra_html_attrs(self) -> dict:
        return {'input_type': 'date'}


class GlueDateTimeField(GlueField):
    type = FieldType.DATETIME

    def extra_html_attrs(self) -> dict:
        return {'input_type': 'datetime-local'}


class GlueDecimalField(GlueField):
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


class GlueEmailField(GlueField):
    type = FieldType.EMAIL

    def extra_html_attrs(self) -> dict:
        return {'input_type': 'email'}


class GlueFloatField(GlueField):
    type = FieldType.FLOAT

    def extra_html_attrs(self) -> dict:
        return {'input_type': 'number'}


class GlueIntegerField(GlueField):
    type = FieldType.INTEGER

    def extra_html_attrs(self) -> dict:
        return {'input_type': 'number'}


class GlueTextField(GlueField):
    type = FieldType.TEXT

    def extra_html_attrs(self) -> dict:
        return {
            'rows': 5,
            'cols': 40,
            'input_type': 'text'
        }
