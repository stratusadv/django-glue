from dataclasses import dataclass, field
from typing import Optional

from django_glue.form.field.attributes.attributes import FieldAttributes


@dataclass
class FormField:
    name: str
    type: str
    attrs: FieldAttributes
    label: Optional[str] = None
    id: Optional[str] = None
    help_text: str = ''
    choices: Optional[list] = field(default_factory=list)

    def __post_init__(self):
        if self.id is None:
            self.id = f'id_{self.name}'

        if self.label is None:
            self.label = ' '.join(self.name.split('_')).title()

    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'type': self.type,
            'attrs': self.attrs.to_dict(),
            'label': self.label,
            'help_text': self.help_text,
            'choices': self.choices
        }
