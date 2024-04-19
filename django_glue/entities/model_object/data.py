from dataclasses import dataclass
from typing import Any


@dataclass
class GlueModelField:
    name: str
    value: Any
    form_field: 'GlueFormField'

    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'value': self.value,
            'form_field': self.form_field.to_dict()
        }
