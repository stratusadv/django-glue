from typing import Optional

from django_glue.form.field.attrs.entities import GlueFieldAttrs
from django_glue.form.field.entities import GlueFormField
from django_glue.form.field.attrs.builder import glue_field_attr_from_model_field


class GlueFormFieldFactory:
    def __init__(self, model_field):
        self.model_field = model_field

    def attrs(self) -> GlueFieldAttrs:
        return glue_field_attr_from_model_field(self.model_field)

    def choices(self) -> list:
        if self.model_field.choices:
            return self.model_field.choices
        else:
            if self.model_field.get_internal_type() == 'BooleanField':
                return [(True, 'Yes'), (False, 'No')]
            else:
                return [(False, '--------------')]

    def factory_method(self):
        return GlueFormField(
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
