"""Mixin for shared model field resolution logic between ModelGlue and QuerySetGlue."""

from __future__ import annotations

from abc import abstractmethod
from functools import cached_property
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from django.db.models.options import Options


class ModelFieldResolutionMixin:
    """Mixin providing shared model field resolution logic for Django model-based Glue objects.

    Subclasses must implement:
        - _model_meta: Property returning the Django model's _meta options
        - fields: Tuple of field names to include (or ALL_FIELDS)
        - exclude: Tuple of field names to exclude (or ALL_FIELDS)
        - globally_excluded_field_types: Frozenset of field types to exclude
    """

    fields: tuple[str, ...] | str
    exclude: tuple[str, ...] | str
    globally_excluded_field_types: frozenset[str]

    @property
    @abstractmethod
    def _model_meta(self) -> Options[Any]:
        """Return the Django model's _meta options."""
        ...

    @cached_property
    def _forward_field_names(self) -> tuple[str, ...]:
        return tuple(
            field.name
            for field in self._model_meta.fields
        )

    @cached_property
    def _forward_field_attnames(self) -> tuple[str, ...]:
        return tuple(
            field.attname
            for field in self._model_meta.fields
            if getattr(field, 'attname', field.name) != field.name
        )

    @cached_property
    def _default_field_names(self) -> tuple[str, ...]:
        return tuple(
            field.attname
            if (
                getattr(field, 'many_to_one', False)
                or getattr(field, 'one_to_one', False)
            )
            else field.name
            for field in self._model_meta.fields
        )

    @cached_property
    def _many_to_many_field_names(self) -> tuple[str, ...]:
        return tuple(
            field.name
            for field in self._model_meta.many_to_many
        )

    @cached_property
    def _reverse_relation_names(self) -> tuple[str, ...]:
        """Get names of reverse relations (reverse FK + reverse M2M)."""
        return tuple(
            rel.get_accessor_name()
            for rel in self._model_meta.related_objects
            if not rel.hidden and rel.get_accessor_name()
        )

    @cached_property
    def _all_available_field_names(self) -> tuple[str, ...]:
        return self._all_available_field_names_for_meta(self._model_meta)

    @staticmethod
    def _all_available_field_names_for_meta(model_meta: Options[Any]) -> tuple[str, ...]:
        forward_field_names = tuple(
            field.name
            for field in model_meta.fields
        )
        forward_field_attnames = tuple(
            field.attname
            for field in model_meta.fields
            if getattr(field, 'attname', field.name) != field.name
        )
        many_to_many_field_names = tuple(
            field.name
            for field in model_meta.many_to_many
        )
        reverse_relation_names = tuple(
            rel.get_accessor_name()
            for rel in model_meta.related_objects
            if not rel.hidden and rel.get_accessor_name()
        )
        return forward_field_names + forward_field_attnames + many_to_many_field_names + reverse_relation_names

    def _get_model_field(self, name: str) -> Any:
        for field in self._model_meta.fields:
            if name in {field.name, getattr(field, 'attname', field.name)}:
                return field
        return self._model_meta.get_field(name)

    def _get_reverse_relation(self, name: str) -> Any:
        """Get the reverse relation object by accessor name, or None if not found."""
        for rel in self._model_meta.related_objects:
            if rel.get_accessor_name() == name:
                return rel
        return None

    def _is_reverse_relation(self, name: str) -> bool:
        """Check if name is a reverse relation accessor."""
        return self._get_reverse_relation(name) is not None

    def _is_field_includable(self, name: str) -> bool:
        """Check if a field name can be included (not a globally excluded type).

        Reverse relations are always includable since they have no field type.
        Forward fields are checked against globally_excluded_field_types.
        """
        if self._is_reverse_relation(name):
            return True
        field = self._get_model_field(name)
        return field.get_internal_type() not in self.globally_excluded_field_types

    @cached_property
    def _included_fields(self) -> list[str]:
        all_names = self._all_available_field_names
        names = self._default_field_names if self.fields == '__all__' or not self.fields else self.fields
        excluded = set(all_names) if self.exclude == '__all__' else set(self.exclude)
        return [
            name
            for name in names
            if name not in excluded
            and self._is_field_includable(name)
        ]
