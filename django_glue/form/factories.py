from abc import ABC

from django.db.models import Field


class GlueAttrFactory(ABC):

    def __init__(self, model_field: Field):
        self.model_field = model_field

    def factory_method(self) -> dict:
        return {
            'html_attrs': self.html_attrs(),
            'field_attrs': self.field_attrs()
        }

    def html_attrs(self) -> dict:
        # Automatically added to field.
        html_attrs = {
            'name': self.model_field.name,
            'id': f'id_{self.model_field.name}',
            # 'help_text': self.model_field.help_text,  # Todo: Was raising an error with proxy field.
        }

        if self.model_field.blank:
            html_attrs['required'] = True

        if self.model_field.hidden:
            html_attrs['hidden'] = True

        return html_attrs


    def field_attrs(self) -> dict:
        # Used by glue field js to set special field attributes.
        return {
            'label': ' '.join(word.capitalize() for word in self.model_field.name.split('_')),
            'choices': self.model_field.choices
        }


class GlueCharAttrFactory(GlueAttrFactory):

    def html_attrs(self) -> dict:
        html_attrs = super().html_attrs()
        html_attrs['maxlength'] = self.model_field.max_length
        return html_attrs
