from dataclasses import dataclass
from typing import Any

from django_glue.form.html_attrs import GlueFieldAttrs


@dataclass
class GlueModelField:
    name: str
    type: str
    value: Any
    glue_field_attrs: GlueFieldAttrs

    def to_dict(self) -> dict:
        return {
                'name': self.name,
                'value': self.value,
                'html_attr': self.glue_field_attrs.html_attrs
            }