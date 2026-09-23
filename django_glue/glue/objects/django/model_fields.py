"""Mixin for shared model field resolution logic between ModelGlue and QuerySetGlue."""

from __future__ import annotations

from abc import abstractmethod
from functools import cached_property
from typing import TYPE_CHECKING, Any, Mapping, Sequence

from django.db.models import QuerySet

from django_glue.access import GlueAccess
from django_glue.glue.objects.django.relation import OwningRelation
from django_glue.glue.queryset_unpickler import (
    _queryset_class_path,
    _resolve_queryset_class,
    model_class_path,
    pickle_query,
    unpickle_query,
)

if TYPE_CHECKING:
    from django.db import models
    from django.db.models.options import Options

    from django_glue.glue.objects.django.model.object import ModelGlue
    from django_glue.glue.objects.django.queryset import QuerySetGlue


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
    _select_related: set[str]
    globally_excluded_field_types: frozenset[str]

    @property
    @abstractmethod
    def _model_meta(self) -> Options[Any]:
        """Return the Django model's _meta options."""
        ...

    @staticmethod
    def _reject_nested_all_marker(names: Sequence[str] | str, param_name: str) -> None:
        """``fields=['__all__']`` is a common typo of ``fields='__all__'``; left
        uncaught, the marker dies deep in Django as an opaque FieldDoesNotExist."""
        if isinstance(names, str) or '__all__' not in names:
            return
        action = 'exclude' if param_name == 'exclude' else 'include'
        msg = (
            f"{param_name} contains '__all__' as an element. "
            f"To {action} every field, pass {param_name}='__all__' "
            f'(or {param_name}=ALL_FIELDS) as the whole argument, '
            'not as an item in a list of field names.'
        )
        raise ValueError(msg)

    def _normalize_choices(
        self,
        choices: Mapping[str, QuerySet] | None,
    ) -> dict[str, QuerySet]:
        """Validate relation choice sources (state-model.md §9): each key names
        an exposed relation and its queryset queries that relation's model."""
        exposed = set(self._included_fields) | {
            relation_name for relation_name, _subfields in self._projected_relations
        }
        normalized: dict[str, QuerySet] = {}
        for field_name, queryset in (choices or {}).items():
            if field_name not in exposed:
                msg = f'choices names {field_name!r}, which is not an exposed relation.'
                raise ValueError(msg)
            related_model = getattr(self._model_meta.get_field(field_name), 'related_model', None)
            if related_model is None:
                msg = f'choices names {field_name!r}, which is not a relation.'
                raise ValueError(msg)
            if not isinstance(queryset, QuerySet):
                msg = f'choices[{field_name!r}] must be a QuerySet.'
                raise TypeError(msg)
            if queryset.model is not related_model:
                msg = (
                    f'choices[{field_name!r}] must query {related_model._meta.label}, '
                    f'not {queryset.model._meta.label}.'
                )
                raise ValueError(msg)
            normalized[field_name] = queryset.all()
        return normalized

    @staticmethod
    def _serialize_choices(choices: Mapping[str, QuerySet]) -> dict[str, dict[str, str]]:
        return {
            field_name: {
                'encoded_queryset': pickle_query(queryset),
                'model_class_path': model_class_path(queryset.model),
                'queryset_class_path': _queryset_class_path(queryset),
            }
            for field_name, queryset in choices.items()
        }

    @staticmethod
    def _deserialize_choices(serialized: Mapping[str, Mapping[str, str]]) -> dict[str, QuerySet]:
        choices: dict[str, QuerySet] = {}
        for field_name, source in serialized.items():
            query = unpickle_query(source['encoded_queryset'], source['model_class_path'])
            queryset = _resolve_queryset_class(source.get('queryset_class_path'))(model=query.model)
            queryset.query = query
            choices[field_name] = queryset
        return choices

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
    def _selected_related_field_names(self) -> tuple[str, ...]:
        return tuple(
            field_name
            for field_name in self._select_related
            if field_name in self._forward_field_names
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
        if name.endswith('_ids'):
            relation_name = name[:-4]
            relation = self._get_reverse_relation(relation_name)
            if relation is None:
                relation = self._model_meta.get_field(relation_name)
            if (
                getattr(relation, 'many_to_many', False)
                or getattr(relation, 'one_to_many', False)
            ):
                return relation
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
        Dotted relation projections are declared separately as addressed
        children, so they are always includable here (validation happens when
        the projection graph is compiled, not in the flat-field filter).
        """
        if '__' in name:
            return True
        if self._is_reverse_relation(name):
            return True
        field = self._get_model_field(name)
        return field.get_internal_type() not in self.globally_excluded_field_types

    @cached_property
    def _projected_relations(self) -> tuple[tuple[str, tuple[str, ...]], ...]:
        """Compile dotted relation projections from ``fields``.

        A field entry such as ``project__id`` or ``project__user__name`` names
        a related scalar leaf and introduces ``project`` as an addressed
        ``ModelGlue`` child (state-model.md §4), while the relation's raw
        identity or membership remains an ordinary value on the owner.
        To-one relations introduce ``ModelGlue`` children and to-many
        relations introduce ``QuerySetGlue`` children. ``fields='__all__'``
        never traverses relations, so it produces no projections.
        """
        if self.fields == '__all__' or not self.fields:
            return ()
        excluded = (
            set(self._all_available_field_names)
            if self.exclude == '__all__'
            else set(self.exclude)
        )
        projections: dict[str, list[str]] = {}
        for name in self.fields:
            if '__' not in name:
                continue
            relation_name, subpath = name.split('__', 1)
            field = self._get_model_field(relation_name)
            if not getattr(field, 'is_relation', False):
                msg = (
                    f'Dotted field {name!r} projects into relation '
                    f'{relation_name!r}, which is not a Django relation.'
                )
                raise ValueError(msg)
            if relation_name in excluded or self._relation_identity_name(
                relation_name
            ) in excluded:
                continue
            projections.setdefault(relation_name, [])
            if subpath not in projections[relation_name]:
                projections[relation_name].append(subpath)
        return tuple(
            (relation_name, tuple(subpaths))
            for relation_name, subpaths in projections.items()
        )

    @cached_property
    def _projected_field_paths(self) -> tuple[str, ...]:
        return tuple(
            f'{relation_name}__{subpath}'
            for relation_name, subpaths in self._projected_relations
            for subpath in subpaths
        )

    @cached_property
    def _projected_to_many_relation_names(self) -> frozenset[str]:
        return frozenset(
            relation_name
            for relation_name, _subfields in self._projected_relations
            if self._relation_is_to_many(relation_name)
        )

    def _relation_identity_name(self, relation_name: str) -> str:
        """Return the owner-side raw identity leaf name for a forward relation."""
        if self._relation_is_to_many(relation_name):
            return f'{relation_name}_ids'
        field = self._get_model_field(relation_name)
        return getattr(field, 'attname', relation_name)

    def _relation_is_nullable(self, relation_name: str) -> bool:
        """Whether a to-one relation may resolve to no related object."""
        field = self._get_model_field(relation_name)
        if self._relation_is_to_many(relation_name):
            return False
        if self._is_reverse_relation(relation_name):
            return True
        return bool(getattr(field, 'null', False))

    def _relation_is_to_many(self, relation_name: str) -> bool:
        field = self._get_model_field(relation_name)
        return bool(
            getattr(field, 'many_to_many', False)
            or getattr(field, 'one_to_many', False)
        )

    def _related_queryset(self, instance: models.Model, relation_name: str) -> QuerySet:
        """The members of a saved instance's to-many relation. A reverse
        foreign key filters on the owner's pk: its related manager filters on
        the owner instance itself, which the signed query cannot carry
        through the queryset unpickler."""
        relation = self._get_reverse_relation(relation_name)
        if relation is not None and relation.one_to_many:
            return relation.related_model._default_manager.filter(
                **{relation.field.name: instance.pk},
            )
        return getattr(instance, relation_name).all()

    def _construct_relation_child(
        self,
        related: models.Model | QuerySet,
        *,
        owner: models.Model,
        relation_name: str,
        name: str,
        subfields: tuple[str, ...],
    ) -> ModelGlue | QuerySetGlue:
        """Construct the unbound child backing a projected relation.

        Shared by both ownership modes (state-model.md §4): a standalone
        owner builds a child from its own instance, while a collection builds
        one shared child per unique related object across its rows. The
        relation's projection limits what the child exposes.

        To-one children default to ``VIEW`` -- editing a shared address must
        be explicit. A to-many child also defaults to ``VIEW``, but when the
        introducing model or queryset has ``ADD`` or stronger access and the
        relation can attach a new member (``OwningRelation.creatable``) it
        receives exactly ``ADD`` (never implicit ``CHANGE`` or ``DELETE``), so
        ``relation.new()`` is available while persisted members stay
        read-only (ADR 009).
        """
        from django_glue.glue.objects.django.model.object import (  # noqa: PLC0415
            ModelGlue,
        )

        if isinstance(related, QuerySet):
            from django_glue.glue.objects.django.queryset import (  # noqa: PLC0415
                QuerySetGlue,
            )

            relation = (
                OwningRelation.creatable(owner, relation_name)
                if self.access.has_access(GlueAccess.ADD)
                else None
            )
            child = QuerySetGlue(
                related,
                name=name,
                access=GlueAccess.VIEW if relation is None else GlueAccess.ADD,
                fields=tuple(subfields),
            )
            child._relation = relation
            return child

        return ModelGlue(
            related,
            name=name,
            access=GlueAccess.VIEW,
            fields=tuple(subfields),
        )

    def cap_access(self, ceiling: GlueAccess) -> None:
        """The derived editable projection is access-gated, so a capped object
        re-derives it from its declaration."""
        super().cap_access(ceiling)  # type: ignore[misc]
        self.editable = self._normalize_editable(self._editable_declaration, self.access)
        self._invalidate_attributes()  # type: ignore[attr-defined]

    def _normalize_editable(
        self,
        editable: Sequence[str] | None,
        access: GlueAccess,
    ) -> tuple[str, ...]:
        if editable is None:
            selected = tuple(
                name
                for name in self._included_fields
                if self._is_concrete_editable_field(name)
            )
        else:
            projected_names = {
                relation_name
                for relation_name, _subfields in self._projected_relations
            }
            # A raw forward-relation identity is named by its exposed path
            # (the attname) once the relation is projected as an addressed
            # child, so an explicit `editable=['project']` entry maps to the
            # same leaf (state-model.md §9).
            selected = tuple(
                self._relation_identity_name(name)
                if name in projected_names
                else name
                for name in dict.fromkeys(editable)
            )
            unexposed = tuple(
                name
                for name in selected
                if name not in self._included_fields
            )
            if unexposed:
                msg = f'Editable fields must be exposed: {unexposed!r}.'
                raise ValueError(msg)
            primary_keys = {self._model_meta.pk.name, self._model_meta.pk.attname}
            if primary_keys & set(selected):
                msg = (
                    'The primary key is the signed target identity and is never '
                    'client-editable.'
                )
                raise ValueError(msg)
            invalid = tuple(
                name
                for name in selected
                if not self._is_concrete_editable_field(name)
            )
            if invalid:
                msg = f'Editable fields must be concrete Django-editable fields: {invalid!r}.'
                raise ValueError(msg)

        if not access.has_access(GlueAccess.ADD):
            return ()
        return selected

    def _is_concrete_editable_field(self, name: str) -> bool:
        if self._is_reverse_relation(name):
            return False
        field = self._get_model_field(name)
        return bool(
            (field.concrete or getattr(field, 'many_to_many', False))
            and field.editable
            and not getattr(field, 'primary_key', False)
        )

    @cached_property
    def _included_fields(self) -> list[str]:
        all_names = self._all_available_field_names
        if self.fields == '__all__' or not self.fields:
            names = self._default_field_names + self._many_to_many_field_names
        else:
            names = self.fields
        excluded = set(all_names) if self.exclude == '__all__' else set(self.exclude)
        included = []
        seen = set()
        for name in names:
            # Dotted relation projections are addressed children declared
            # separately; the relation's raw identity leaf is added below.
            if '__' in name:
                continue
            if (
                name in seen
                or name in excluded
                or not self._is_field_includable(name)
            ):
                continue
            included.append(name)
            seen.add(name)
        for relation_name, _subfields in self._projected_relations:
            identity_name = self._relation_identity_name(relation_name)
            if (
                identity_name in seen
                or identity_name in excluded
                or not self._is_field_includable(identity_name)
            ):
                continue
            included.append(identity_name)
            seen.add(identity_name)
        pk_name = self._model_meta.pk.name
        pk_attname = self._model_meta.pk.attname
        if not {pk_name, pk_attname} & (seen | excluded):
            included.insert(0, pk_name)
        return included
