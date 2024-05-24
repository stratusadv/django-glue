from abc import ABC, abstractmethod
from typing import Union

from django.db.models import Field

from django_glue.form.enums import GlueAttrType
from django_glue.form.html_attrs import GlueFieldAttrs, GlueFieldAttr


class GlueAttrFactory(ABC):

    def __init__(self, model_field: Field):
        self.model_field = model_field
        self.glue_field_attrs = GlueFieldAttrs()

    def add_attr(
            self,
            name: str,
            value: Union[str, int, bool, None],
            attr_type: GlueAttrType
    ) -> None:
        attr = GlueFieldAttr(name=name, value=value, attr_type=attr_type)
        self.glue_field_attrs += attr

    @abstractmethod
    def add_field_attrs(self):
        pass

    def add_base_attrs(self):
        self.add_attr('name', self.model_field.name, GlueAttrType.HTML)
        self.add_attr('id', f'id_{self.model_field.name}', GlueAttrType.HTML)
        self.add_attr('label', str(self.model_field.verbose_name).title(), GlueAttrType.FIELD)

        if not self.model_field.blank:
            self.add_attr('required', True, GlueAttrType.HTML)

        # Todo: Need to deal with hidden. The label shouldn't show if it is hidden...
        # if self.model_field.hidden:
        #     self.add_attr('hidden', True, GlueAttrType.HTML)

        if self.model_field.help_text:
            self.add_attr('help_text', str(self.model_field.help_text), GlueAttrType.FIELD)

        if self.model_field.choices:
            self.add_attr('choices', self.model_field.choices, GlueAttrType.FIELD)

    def factory_method(self) -> GlueFieldAttrs:
        self.glue_field_attrs = GlueFieldAttrs()
        self.add_base_attrs()
        self.add_field_attrs()
        return self.glue_field_attrs


class GlueCharAttrFactory(GlueAttrFactory):
    def add_field_attrs(self):
        if self.model_field.max_length:
            self.add_attr('maxlength', self.model_field.max_length, GlueAttrType.HTML)


class GlueTextAreaAttrFactory(GlueAttrFactory):
    def add_field_attrs(self):
        self.add_attr('cols', 20, GlueAttrType.HTML)
        self.add_attr('rows', 3, GlueAttrType.HTML)

        if self.model_field.max_length:
            self.add_attr('maxlength', self.model_field.max_length, GlueAttrType.HTML)


class GlueIntegerAttrFactory(GlueTextAreaAttrFactory):
    def add_field_attrs(self):
        self.add_attr('step', 1, GlueAttrType.HTML)
        valid_range = range(-999999999, 999999999) # This is an arbitrary number. Django default creates errors.
        default_validators = ['min_value', 'max_value']
        for validator in self.model_field.validators:

            if validator.code in default_validators:

                if validator.limit_value in valid_range:
                    self.add_attr(validator.code.split('_')[-1], validator.limit_value, GlueAttrType.HTML)
                else:
                    self.add_attr('min', None, GlueAttrType.HTML)

