from dataclasses import dataclass, field
from typing import Optional

from django_glue.form.field.attrs.entities import GlueFieldAttrs


@dataclass
class GlueFormField:
    name: str
    type: str
    attrs: GlueFieldAttrs
    label: Optional[str]
    help_text: str = ''
    choices: Optional[list] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'type': self.type,
            'attrs': self.attrs.to_dict(),
            'label': self.label,
            'help_text': self.help_text,
            'choices': self.choices
        }
