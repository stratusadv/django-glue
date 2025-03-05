from typing import Optional

from django_glue.form.field.attributes.attributes import FieldAttributes
from django_glue.form.field.field import FormField
from django_glue.form.field.attributes.builder import field_attr_from_model_field


class FormFieldFactory:
    def __init__(self, model_field):
        self.model_field = model_field

    def attrs(self) -> FieldAttributes:
        return field_attr_from_model_field(self.model_field)

    def choices(self) -> list:
        if self.model_field.choices:
            if self.model_field.blank:
                return [(False, '----------')] + self.model_field.choices
            else:
                return self.model_field.choices
        else:
            if self.model_field.get_internal_type() == 'BooleanField':
                return [(True, 'Yes'), (False, 'No')]
            else:
                return [(False, '----------')]

    def factory_method(self):
        return FormField(
            name=self.model_field.name,
            type=self.model_field.get_internal_type(),
            label=self.label(),
            help_text=self.help_text(),
            choices=self.choices(),
            attrs=self.attrs()
        )

    def help_text(self) -> str:
        if self.model_field.hidden or not self.model_field.help_text:
            return ''
        else:
            return str(self.model_field.help_text) if self.model_field.help_text else None

    def label(self) -> Optional[str]:
        if self.model_field.hidden:
            return None
        else:
            return str(self.model_field.verbose_name).title()
