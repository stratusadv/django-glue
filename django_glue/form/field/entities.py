from dataclasses import dataclass


@dataclass
class GlueFormField:
    name: str
    type: str
    attrs: dict  # Or is this a list?

    def to_dict(self):
        pass
