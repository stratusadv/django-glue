from dataclasses import dataclass, field
from typing import Union, Self


@dataclass
class FieldAttribute:
    name: str
    value: Union[str, int, bool, None] = None

    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'value': self.value
        }


@dataclass
class FieldAttributes:
    attrs: list[FieldAttribute] = field(default_factory=list)

    def __add__(self, other) -> Self:
        if isinstance(other, FieldAttributes):
            combined_attrs = self._merge_attrs(other.attrs)
        elif isinstance(other, FieldAttribute):
            combined_attrs = self._merge_attrs([other])
        else:
            raise TypeError(f'Unsupported type "{type(other)}"')
        return FieldAttributes(attrs=combined_attrs)

    def _merge_attrs(self, new_attrs: list[FieldAttribute]) -> list[FieldAttribute]:
        attr_dict: dict[str, FieldAttribute] = {attr.name: attr for attr in self.attrs}
        for attr in new_attrs:
            attr_dict[attr.name] = attr
        return list(attr_dict.values())

    def to_dict(self) -> list:
        return [attr.to_dict() for attr in self.attrs]
