from dataclasses import dataclass, field
from typing import Union

from django_glue.form.enums import GlueAttrType


# Todo: Delete this file and move into factories.


@dataclass
class GlueFieldAttr:
    name: str
    attr_type: GlueAttrType
    value: Union[str, int, bool, None] = None

    def to_dict(self) -> dict:
        return {
            self.name: {
                'attr_type': self.attr_type.value,
                'value': self.value
            }
        }


@dataclass
class GlueFieldAttrs:
    attrs: list[GlueFieldAttr] = field(default_factory=list)

    def __add__(self, other):
        if isinstance(other, GlueFieldAttrs):
            combined_attrs = self._merge_attrs(other.attrs)
        elif isinstance(other, GlueFieldAttr):
            combined_attrs = self._merge_attrs([other])
        else:
            raise TypeError(f'Unsupported type "{type(other)}"')
        return GlueFieldAttrs(attrs=combined_attrs)

    def _merge_attrs(self, new_attrs: list[GlueFieldAttr]) -> list[GlueFieldAttr]:
        attr_dict: dict[str, GlueFieldAttr] = {attr.name: attr for attr in self.attrs}
        for attr in new_attrs:
            attr_dict[attr.name] = attr
        return list(attr_dict.values())

    def to_dict(self) -> dict:
        attr_dict = {}

        for attr in self.attrs:
            attr_dict.update(attr.to_dict())

        return attr_dict
