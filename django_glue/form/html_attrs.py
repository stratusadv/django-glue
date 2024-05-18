from dataclasses import dataclass, field
from typing import Union

from django_glue.form.enums import GlueAttrType


# Todo: Delete this file and move into factories.


@dataclass
class GlueFieldAttr:
    name: str
    attr_type: GlueAttrType
    value: Union[str, int, bool, None] = None

    def to_dict(self) -> dict:
        return {
            self.name: {
                'attr_type': self.attr_type.value,
                'value': self.value
            }
        }


@dataclass
class GlueFieldAttrs:
    attrs: list[GlueFieldAttr] = field(default_factory=list)

    def __add__(self, other):
        if isinstance(other, GlueFieldAttrs):
            return GlueFieldAttrs(attrs=self.attrs + other.attrs)
        elif isinstance(other, GlueFieldAttr):
            return GlueFieldAttrs(attrs=self.attrs + [other])
        else:
            raise TypeError(f'Unsupported type "{type(other)}"')

    def to_dict(self) -> dict:
        attr_dict = {}

        for attr in self.attrs:
            attr_dict.update(attr.to_dict())

        return attr_dict

#
# class GlueBooleanFieldAttr(GlueFieldAttrs):
#     type = FieldType.BOOLEAN
#
#
# class GlueCharFieldAttr(GlueFieldAttrs):
#     type = FieldType.CHAR
#
#     def __init__(self, max_length: int, **kwargs):
#         super().__init__(**kwargs)
#         self.max_length = max_length
#
#     def extra_html_attrs(self) -> dict:
#         return {
#             'maxlength': self.max_length,
#             'type': 'text'
#         }
#
#
# class GlueDateFieldAttr(GlueFieldAttrs):
#     type = FieldType.DATE
#
#     def extra_html_attrs(self) -> dict:
#         return {'input_type': 'date'}
#
#
# class GlueDateTimeFieldAttr(GlueFieldAttrs):
#     type = FieldType.DATETIME
#
#     def extra_html_attrs(self) -> dict:
#         return {'input_type': 'datetime-local'}
#
#
# class GlueDecimalFieldAttr(GlueFieldAttrs):
#     type = FieldType.DECIMAL
#
#     def __init__(self, max_digits: int, decimal_places: int, **kwargs):
#         super().__init__(**kwargs)
#         self.max_digits = max_digits
#         self.decimal_places = decimal_places
#
#     def extra_html_attrs(self) -> dict:
#         return {
#             'max_digits': self.max_digits,
#             'decimal_places': self.decimal_places,
#             'input_type': 'number'
#         }
#
#
# class GlueEmailFieldAttr(GlueFieldAttrs):
#     type = FieldType.EMAIL
#
#     def extra_html_attrs(self) -> dict:
#         return {'input_type': 'email'}
#
#
# class GlueFloatFieldAttr(GlueFieldAttrs):
#     type = FieldType.FLOAT
#
#     def extra_html_attrs(self) -> dict:
#         return {'input_type': 'number'}
#
#
# class GlueIntegerFieldAttr(GlueFieldAttrs):
#     type = FieldType.INTEGER
#
#     def extra_html_attrs(self) -> dict:
#         return {'input_type': 'number'}
#
#
# class GlueTextFieldAttr(GlueFieldAttrs):
#     type = FieldType.TEXT
#
#     def extra_html_attrs(self) -> dict:
#         return {
#             'rows': 5,
#             'cols': 40,
#             'input_type': 'text'
#         }
