from abc import ABC
from typing import Union

from django_glue.form.enums import FieldType


class GlueFieldAttrs(ABC):
    type = None

    def __init__(
            self,
            name: str,
            required: bool = False,
            hidden: bool = False,
            help_text: str = '',
            disabled: bool = True,
            choices: Union[list, tuple, None] = None
    ):
        if self.type is None:
            raise Exception(f"Field {self.__class__.__name__} has no type")

        self.required = required
        self.disabled = disabled
        self.hidden = hidden
        self.name = name
        self.help_text = help_text
        self.choices = choices

    @property
    def html_attrs(self):
        return self.base_html_attrs() | self.extra_html_attrs()

    def base_html_attrs(self) -> dict:
        return {
            'required': self.required,
            'hidden': self.hidden,
            'label': ' '.join(word.capitalize() for word in self.name.split('_')),
            'id': f'id_{self.name}',
            'help_text': self.help_text,
            'disabled': self.disabled,
            'choices': self.choices
        }

    def extra_html_attrs(self) -> dict:
        return {}


class GlueBooleanFieldAttr(GlueFieldAttrs):
    type = FieldType.BOOLEAN


class GlueCharFieldAttr(GlueFieldAttrs):
    type = FieldType.CHAR

    def __init__(self, max_length: int, **kwargs):
        super().__init__(**kwargs)
        self.max_length = max_length

    def extra_html_attrs(self) -> dict:
        return {
            'maxlength': self.max_length,
            'type': 'text'
        }


class GlueDateFieldAttr(GlueFieldAttrs):
    type = FieldType.DATE

    def extra_html_attrs(self) -> dict:
        return {'input_type': 'date'}


class GlueDateTimeFieldAttr(GlueFieldAttrs):
    type = FieldType.DATETIME

    def extra_html_attrs(self) -> dict:
        return {'input_type': 'datetime-local'}


class GlueDecimalFieldAttr(GlueFieldAttrs):
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


class GlueEmailFieldAttr(GlueFieldAttrs):
    type = FieldType.EMAIL

    def extra_html_attrs(self) -> dict:
        return {'input_type': 'email'}


class GlueFloatFieldAttr(GlueFieldAttrs):
    type = FieldType.FLOAT

    def extra_html_attrs(self) -> dict:
        return {'input_type': 'number'}


class GlueIntegerFieldAttr(GlueFieldAttrs):
    type = FieldType.INTEGER

    def extra_html_attrs(self) -> dict:
        return {'input_type': 'number'}


class GlueTextFieldAttr(GlueFieldAttrs):
    type = FieldType.TEXT

    def extra_html_attrs(self) -> dict:
        return {
            'rows': 5,
            'cols': 40,
            'input_type': 'text'
        }
