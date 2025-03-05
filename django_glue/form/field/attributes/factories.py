from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any

from django.db.models import Field

from django_glue.form.field.attributes.attributes import FieldAttributes, FieldAttribute


class BaseAttributeFactory(ABC):
    def __init__(self, model_field: Field):
        self.model_field = model_field
        self.glue_field_attrs = FieldAttributes()

    def add_attr(
            self,
            name: str,
            value: Any,
    ) -> None:
        attr = FieldAttribute(name=name, value=value)
        self.glue_field_attrs += attr

    @abstractmethod
    def add_field_attrs(self):
        pass

    def add_base_attrs(self):
        self.add_attr('name', self.model_field.name)
        self.add_attr('id', f'id_{self.model_field.name}')

        if not self.model_field.blank:
            self.add_attr('required', True)

        if self.model_field.hidden:
            self.add_attr('hidden', True)

        if self.model_field.max_length:
            self.add_attr('maxlength', self.model_field.max_length)

    def factory_method(self) -> FieldAttributes:
        self.glue_field_attrs = FieldAttributes()
        self.add_base_attrs()
        self.add_field_attrs()
        return self.glue_field_attrs


class BooleanAttributeFactory(BaseAttributeFactory):
    def add_field_attrs(self):
        pass


class CharAttributeFactory(BaseAttributeFactory):
    def add_field_attrs(self):
        pass


class DateAttributeFactory(BaseAttributeFactory):
    def add_field_attrs(self):
        self.add_attr('max', '')
        self.add_attr('min', '')


class TextAreaAttributeFactory(BaseAttributeFactory):
    def add_field_attrs(self):
        self.add_attr('cols', 20)
        self.add_attr('rows', 3)

        if self.model_field.max_length:
            self.add_attr('maxlength', self.model_field.max_length)


class IntegerAttributeFactory(TextAreaAttributeFactory):
    def add_field_attrs(self):
        self.max_min_validation_attr()
        self.step_attr()

    def max_min_validation_attr(self):
        """
            The range is between Number.MIN_SAFE_INTEGER and Number.MAX_SAFE_INTEGER
            represents Javascript integer limits.
        """
        MIN_SAFE_INTEGER = -9007199254740991
        MAX_SAFE_INTEGER = 9007199254740991
        min_max_validators = {'min_value', 'max_value'}

        for validator in self.model_field.validators:
            if hasattr(validator, 'code') and validator.code in min_max_validators:
                attr_name = validator.code.split('_')[0]

                limit_value = (
                    validator.limit_value
                    if MIN_SAFE_INTEGER <= validator.limit_value <= MAX_SAFE_INTEGER
                    else None
                )

                self.add_attr(attr_name, limit_value)

    def step_attr(self):
        self.add_attr('step', 1)


class DecimalAttributeFactory(IntegerAttributeFactory):
    def add_field_attrs(self):
        super().add_field_attrs()

    def step_attr(self):
        validator = next((v for v in self.model_field.validators if hasattr(v, 'decimal_places')), None)

        if validator:
            step_value = Decimal('1') / (10 ** validator.decimal_places)
            self.add_attr('step', float(step_value))
        else:
            self.add_attr('step', 0.01)
