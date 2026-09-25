from __future__ import annotations

import builtins
from enum import StrEnum
from functools import cached_property
from typing import TYPE_CHECKING, Any, Literal, Mapping, Sequence

from django_glue.access import GlueAccess
from django_glue.conf import settings
from django_glue.exceptions import (
    GlueModelInstanceNotFoundError,
    GlueQuerySetFilterValidationError,
    GlueQuerySetSliceValidationError,
    GlueRequestError,
    GlueRequestErrorCode,
)
from django_glue.glue import address
from django_glue.glue.attributes import DeclaredAttribute
from django_glue.glue.children import BoundGlueChild
from django_glue.glue.collection import BaseCollectionGlue
from django_glue.glue.objects.django.computed_attributes import (
    ComputedAttribute,
    GlueComputedAttributesMixin,
)
from django_glue.glue.objects.django.cursor import (
    GlueCollectionCursor,
    ensure_stable_seek_ordering_on_queryset,
)
from django_glue.glue.objects.django.form.mixin import ModelGlueFormConfigMixin
from django_glue.glue.objects.django.model.object import (
    ALL_FIELDS,
    ModelGlue,
)
from django_glue.glue.objects.django.model_fields import ModelFieldResolutionMixin
from django_glue.glue.objects.django.relation import OwningRelation
from django_glue.glue.operation import GlueOperation, GlueOperationKind
from django_glue.glue.queryset_unpickler import (
    _queryset_class_path,
    _resolve_queryset_class,
    model_class_path,
    pickle_query,
    unpickle_query,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from django import forms
    from django.db import models

    from django_glue.glue.base import BaseGlue
    from django_glue.glue.policy import GluePolicy

DEFAULT_BATCH_SIZE = '__default__'


class WindowChange(StrEnum):
    """How this request changed the loaded row window."""

    REPLACED = 'replaced'
    EXTENDED = 'extended'


class QuerySetGlue(
    GlueComputedAttributesMixin,
    ModelGlueFormConfigMixin,
    ModelFieldResolutionMixin,
    BaseCollectionGlue,
):
    namespace = 'querySet'
    globally_excluded_field_types = ModelGlue.globally_excluded_field_types

    def __init__(
        self,
        queryset: models.QuerySet,
        *,
        name: str | None = None,
        access: GlueAccess = GlueAccess.VIEW,
        fields: Sequence[str] | Literal['__all__'] = (),
        exclude: Sequence[str] | Literal['__all__'] = (),
        editable: Sequence[str] | None = None,
        form: forms.ModelForm | None = None,
        forms: Mapping[str, forms.ModelForm] | None = None,
        computed_attributes: Mapping[str, ComputedAttribute] | None = None,
        choices: Mapping[str, models.QuerySet] | None = None,
        batch_size: int | None | Literal['__default__'] = DEFAULT_BATCH_SIZE,
        last_query_params: dict[str, Any] | None = None,
        loaded_row_count: int = 0,
    ) -> None:
        super().__init__(name=name, access=access)
        self.queryset = queryset
        self.batch_size = self._resolve_batch_size(batch_size)
        self.fields = (
            fields if fields == ALL_FIELDS else tuple(fields)
        )
        self.exclude = (
            exclude if exclude == ALL_FIELDS else tuple(exclude)
        )

        self._reject_nested_all_marker(self.fields, 'fields')
        self._reject_nested_all_marker(self.exclude, 'exclude')

        if not self.fields and not self.exclude:
            msg = 'QuerySetGlue requires at least one of fields or exclude.'
            raise ValueError(msg)

        self.forms = self.normalize_forms(form, forms)
        self._select_related = self._get_select_related_fields()
        self.choices = self._normalize_choices(choices)
        self._editable_declaration = editable
        self.editable = self._normalize_editable(
            editable,
            self.access,
        )
        self.initialize_computed_attributes(computed_attributes)
        self._last_query_params = last_query_params
        self._loaded_row_count = loaded_row_count
        self._current_batch: list[models.Model] = []
        self._window_change: WindowChange | None = None
        # Internal, signed for a projected to-many relation that can attach a
        # new member: drafts from new() save into exactly this relation.
        self._relation: OwningRelation | None = None

    @staticmethod
    def _resolve_batch_size(batch_size: int | None | Literal['__default__']) -> int | None:
        if batch_size == DEFAULT_BATCH_SIZE:
            batch_size = settings.DJANGO_GLUE_QUERYSET_BATCH_SIZE

        if batch_size is None:
            return None

        if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size < 1:
            msg = f'QuerySetGlue batch_size must be a positive integer or None, got {batch_size!r}.'
            raise ValueError(msg)

        return batch_size

    def get_identity(self) -> dict[str, Any]:
        identity = {
            'model_class_path': model_class_path(self.queryset.model),
            'encoded_queryset': pickle_query(self.queryset),
            'queryset_class_path': _queryset_class_path(self.queryset),
            'pk_field_name': self.queryset.model._meta.pk.name,
            'fields': self.fields,
            'exclude': self.exclude,
            'batch_size': self.batch_size,
            'editable': self.editable,
        }
        if self.forms:
            identity['form_identities'] = self.serialize_forms(self.forms)
        if self.choices:
            identity['choices'] = self._serialize_choices(self.choices)
        if self._projected_field_paths:
            identity['projected_fields'] = self._projected_field_paths
        if self._relation is not None:
            identity['relation'] = self._relation.serialize()
        identity |= self.computed_attributes_identity()

        return identity

    def get_attribute_providers(self) -> tuple[Any, ...]:
        # Mirrors ModelGlue's {'instance': self.instance} -- a `@Glue.attr`
        # declared directly on the queryset's class (e.g. a custom
        # QuerySet subclass passed to `objects = MyQuerySet.as_manager()`)
        # is picked up automatically, bound to this exact, already-filtered
        # queryset instance as `self` inside the method.
        return (self.queryset,)

    @property
    def _model_meta(self) -> Any:
        """Return the Django model's _meta options."""
        return self.queryset.model._meta

    def _get_select_related_fields(self) -> set[str]:
        select_related = self.queryset.query.select_related
        if isinstance(select_related, dict):
            # TODO: Preserve nested select_related paths instead of only top-level fields.
            return set(select_related.keys())
        return set()

    def _retained_state(self) -> dict[str, Any]:
        """Query cursor memory is a non-parameterized reconstructor: the next
        batch needs it, and only the server advances it (state-model.md §2)."""
        retained = super()._retained_state()
        retained.update({
            'last_query_params': self._last_query_params,
            'loaded_row_count': self._loaded_row_count,
        })
        return retained

    def get_state(self) -> dict[str, Any]:
        return self._query()

    def _refreshed_output(self) -> dict[str, Any]:
        """Rows answer a query, so a queryset's introduction carries none; a
        refresh re-derives the loaded window alongside the rest of its output
        (state-model.md §10)."""
        return {**super()._refreshed_output(), **self._loaded_window()}

    def _loaded_window(self) -> dict[str, Any]:
        """Re-run the signed last query over the rows already loaded (at least
        one batch) without advancing the cursor, so a refresh neither shrinks
        nor resets a scrolled or paged list (state-model.md §10)."""
        params = self._last_query_params or {}
        queryset = self._filtered_and_ordered(params.get('filter'), params.get('order_by'))
        self._window_change = WindowChange.REPLACED
        if self.batch_size is None:
            self._current_batch = list(queryset)
            return {
                'items': [self._row_address(instance) for instance in self._current_batch],
                'seek_key': None,
                'has_next': False,
                'batch_size': None,
            }
        window = GlueCollectionCursor(queryset, max(self._loaded_row_count, self.batch_size)).seek()
        self._current_batch = list(window.items)
        return {
            'items': [self._row_address(instance) for instance in self._current_batch],
            'seek_key': window.next_seek_key,
            'has_next': window.has_next,
            'batch_size': self.batch_size,
        }

    @cached_property
    def _orm_annotation_names(self) -> tuple[str, ...]:
        return tuple(self.queryset.query.annotations)

    @classmethod
    def _reconstruct_from_policy(cls, policy: GluePolicy) -> QuerySetGlue:
        queryset = cls._decode_queryset_query(
            policy.identity['encoded_queryset'],
            policy.identity['model_class_path'],
            policy.identity.get('queryset_class_path'),
        )
        forms = cls.deserialize_form_classes(
            policy.identity.get('form_identities', {})
        )
        glue_object = cls(
            queryset,
            name=policy.name,
            access=policy.access,
            fields=policy.identity['fields'],
            exclude=policy.identity['exclude'],
            editable=policy.identity['editable'],
            forms=forms,
            computed_attributes=policy.identity.get('computed_attributes', {}),
            batch_size=policy.identity.get('batch_size'),
            last_query_params=policy.state_snapshot.get('last_query_params'),
            loaded_row_count=policy.state_snapshot.get('loaded_row_count', 0),
        )
        # Restored post-construction from the signed (already-validated) policy,
        # so it does not go back through __init__ normalization.
        glue_object.choices = cls._deserialize_choices(policy.identity.get('choices', {}))
        if 'relation' in policy.identity:
            glue_object._relation = OwningRelation.deserialize(policy.identity['relation'])
        return glue_object

    @staticmethod
    def _decode_queryset_query(
        encoded_query: str,
        expected_model_path: str,
        queryset_class_path: str | None = None,
    ) -> models.QuerySet:
        query = unpickle_query(encoded_query, expected_model_path)
        queryset = _resolve_queryset_class(queryset_class_path)(model=query.model)
        queryset.query = query
        return queryset

    @DeclaredAttribute(required_access=GlueAccess.VIEW)
    def query_with_params(
        self,
        filter: dict[str, Any] | None = None,  # noqa: A002
        order_by: str | list[str] | None = None,
        slice: dict[str, Any] | None = None,  # noqa: A002
        seek_key: str | None = None,
        with_total: bool = False,
    ) -> dict[str, Any]:
        return self._query(filter=filter, order_by=order_by, slice=slice, seek_key=seek_key, with_total=with_total)

    def _filtered_and_ordered(
        self,
        filter: dict[str, Any] | None = None,  # noqa: A002
        order_by: str | list[str] | None = None,
    ) -> models.QuerySet:
        queryset = self.queryset
        allowed_fields = set(self._included_fields)

        for key in (filter or {}):
            base_field = key.split('__')[0]
            if base_field not in allowed_fields:
                raise GlueQuerySetFilterValidationError(base_field, list(allowed_fields))

        if filter:
            queryset = queryset.filter(**filter)

        if order_by:
            if isinstance(order_by, str):
                order_by = [order_by]

            queryset = queryset.order_by(*self._nulls_last_order_by(order_by))

        return queryset

    @staticmethod
    def _nulls_last_order_by(order_by: Sequence[str]) -> list[Any]:
        """Convert plain '-field'/'field' order_by strings into expressions that pin NULLs last.

        Seeking past a NULL needs the WHERE clause and the real SQL ordering to
        agree on where NULLs sort -- that's backend-dependent otherwise (e.g.
        SQLite puts NULL first for ascending, Postgres puts it last), so this
        pins it explicitly rather than relying on either default. See
        `GlueCollectionCursor._seek_filter` for the matching WHERE-clause side.
        """
        from django.db.models import F  # noqa: PLC0415

        expressions = []
        for entry in order_by:
            if entry.startswith('-'):
                expressions.append(F(entry[1:]).desc(nulls_last=True))
            else:
                expressions.append(F(entry).asc(nulls_last=True))

        return expressions

    def _query(
        self,
        filter: dict[str, Any] | None = None,  # noqa: A002
        order_by: str | list[str] | None = None,
        slice: dict[str, Any] | None = None,  # noqa: A002
        seek_key: str | None = None,
        with_total: bool = False,
    ) -> dict[str, Any]:
        query_params = {'filter': filter, 'order_by': order_by}
        if query_params != self._last_query_params:
            self._last_query_params = query_params
            self._loaded_row_count = 0
        self._window_change = WindowChange.REPLACED if seek_key is None else WindowChange.EXTENDED

        queryset = self._filtered_and_ordered(filter, order_by)
        total = queryset.count() if with_total else None

        if slice:
            queryset = ensure_stable_seek_ordering_on_queryset(queryset)

        if slice and self.batch_size is not None:
            # `stop` must be given explicitly: an omitted `stop` used to fall
            # back to 0 here (`slice.get('stop') or 0`), which made the width
            # come out non-positive and silently skip this check entirely --
            # letting an open-ended slice through with no bound at all.
            start = slice.get('start') or 0
            stop = slice.get('stop')
            width = None if stop is None else stop - start
            max_width = max(self._loaded_row_count, self.batch_size)
            if width is None or width > max_width:
                raise GlueQuerySetSliceValidationError(width, max_width)

        # Only apply the requested window as an OFFSET/LIMIT on the request
        # that establishes it (no seek_key yet). Django can't `.filter()` a
        # queryset that's already been sliced, so a continuation call instead
        # keeps seeking from wherever it left off via the WHERE-based cursor
        # in seek_batch() below, rather than re-slicing on top of it.
        if slice and seek_key is None:
            queryset = queryset[builtins.slice(slice.get('start'), slice.get('stop'))]

        result = self.seek_batch(queryset, seek_key)
        if with_total:
            result['total'] = total

        return result

    @DeclaredAttribute(required_access=GlueAccess.VIEW)
    def count(
        self,
        filter: dict[str, Any] | None = None,  # noqa: A002
    ) -> int:
        """Return the number of rows matching `filter` on the server.

        Not part of query_with_params()/seek_batch() -- computing this always
        costs a COUNT(*), so it's only ever run when explicitly called, never
        as a side effect of loading a batch.
        """
        return self._filtered_and_ordered(filter).count()

    def seek_batch(
        self,
        objects: models.QuerySet | Sequence[models.Model],
        seek_key: str | None = None,
    ) -> dict[str, Any]:
        if self.batch_size is None:
            self._current_batch = list(objects)
            items = [self._row_address(instance) for instance in self._current_batch]
            self._loaded_row_count += len(items)

            return {'items': items, 'seek_key': None, 'has_next': False, 'batch_size': None}

        cursor = GlueCollectionCursor(objects, self.batch_size)
        batch = cursor.seek(seek_key)
        self._current_batch = list(batch.items)
        self._loaded_row_count += len(batch.items)

        return {
            'items': [self._row_address(instance) for instance in batch.items],
            'seek_key': batch.next_seek_key,
            'has_next': batch.has_next,
            'batch_size': self.batch_size,
        }

    @DeclaredAttribute(required_access=GlueAccess.VIEW)
    def get(self, pk: Any) -> ModelGlue:
        # A pk outside this queryset is a routine client outcome, not a server fault: a
        # row can leave the bound filter between render and refresh. Report it as 404 so
        # callers can tell "not in this collection" apart from a genuine failure.
        try:
            instance = self.queryset.get(pk=pk)
        except self.queryset.model.DoesNotExist as error:
            raise GlueModelInstanceNotFoundError(
                model_name=self.queryset.model._meta.label,
                pk=pk,
            ) from error

        return self._row_glue(instance, bind=False)

    @DeclaredAttribute(required_access=GlueAccess.ADD)
    def new(self, initial: dict | None = None) -> ModelGlue:
        # ADD admits creating a draft, not expanding it: the fields a client may
        # pre-fill are exactly the fields the signed policy marks editable
        # (state-model.md §3, ADR 010).
        if initial:
            disallowed = sorted(set(initial) - set(self.editable))
            if disallowed:
                raise GlueRequestError(
                    code=GlueRequestErrorCode.INVALID_KWARGS,
                    message=(
                        'new(initial) keys are not admitted by the signed '
                        'editable projection.'
                    ),
                    details={'keys': disallowed},
                )
        draft = self._row_glue(self.queryset.model(), bind=False)
        if initial:
            draft._load_client_state(initial)
            draft._invalidate_attributes()
        return draft

    def get_keyed_items(self) -> list[tuple[str, BaseGlue]]:
        return [
            (str(instance.pk), self._row_glue(instance))
            for instance in self._current_batch
        ]

    def _membership(
        self,
        live_children: Mapping[str, str],
        produced: Mapping[str, BaseGlue],
    ) -> list[str]:
        """The loaded window: a new, restarted, or refreshed query replaces it;
        a continuation appends to it; any other call carries it forward."""
        if self._window_change is WindowChange.REPLACED:
            return list(produced)
        return [*(key for key in live_children if key not in produced), *produced]

    def _introduced_entries(
        self,
        policy: GluePolicy,
        reintroduce: list[str],
    ) -> list[dict[str, Any]]:
        """Rows answering a query this request participate, so their entries
        ride even when the window's address map is unchanged (state-model.md
        §10 slot table, row 3)."""
        entries = super()._introduced_entries(policy, reintroduce)
        if self._window_change is None:
            return entries
        sent = {entry['address'] for entry in entries}
        return entries + [
            entry for entry in self._serialized_child_entries() if entry['address'] not in sent
        ]

    def _rebuild_item(self, key: str) -> BaseGlue | None:
        instance = self.queryset.filter(pk=key).first()
        return self._row_glue(instance) if instance is not None else None

    def _bind_children(
        self,
        *,
        live_children: Mapping[str, str] | None = None,
        reintroduce: Iterable[str] = (),
    ) -> tuple[BoundGlueChild, ...]:
        row_children = super()._bind_children(
            live_children=live_children,
            reintroduce=reintroduce,
        )
        relation_children = self._bind_relation_children(
            self._current_batch,
            owner_address=self.address,
        )
        relation_paths = {child.path for child in relation_children}
        return tuple(
            child for child in row_children if child.path not in relation_paths
        ) + relation_children

    def _row_glue(self, instance: models.Model, *, bind: bool = True) -> ModelGlue:
        child_name = f'{self.name}.{instance.pk}'
        child_forms = {
            # Need to rebuild the form here in order to properly bind instance data!
            name: form.__class__(instance=instance)
            for name, form in self.forms.items()
        }
        # A draft (new()) is create-in-progress: it requires ADD until its first
        # save; a persisted row takes the collection's row access. An ADD column
        # exposes existing rows as VIEW -- the create permission is pinned to
        # drafts. The row access is signed so reconstruction can settle a draft
        # after its first save.
        row_access = (
            GlueAccess.VIEW
            if self.access == GlueAccess.ADD
            else self.access
        )
        child_access = GlueAccess.ADD if instance.pk is None else row_access
        child_object = ModelGlue(
            instance,
            name=child_name,
            access=child_access,
            fields=tuple(self._included_fields) + self._projected_field_paths,
            editable=self.editable,
            annotations=self._orm_annotation_names,
            forms=child_forms,
            select_related=self._select_related,
            computed_attributes=self.computed_attributes,
            choices=self.choices,
        )
        child_object._row_access = row_access
        child_object.request = self.request
        if instance.pk is None:
            child_object._relation = self._relation
        else:
            child_object._address = address.item(self.address, str(instance.pk))

        relation_paths = {
            relation_name for relation_name, _subfields in self._projected_relations
        }
        bound_children = []
        for child in child_object._bind_children():
            if child.path not in relation_paths:
                bound_children.append(child)
                continue
            relation_name = child.path
            if self._relation_is_to_many(relation_name):
                relation_key = instance.pk
            else:
                related = getattr(instance, relation_name, None)
                if related is None:
                    continue
                relation_key = related.pk
            bound_children.append(BoundGlueChild(
                path=relation_name,
                address=self._relation_child_address(
                    self.address,
                    relation_name,
                    relation_key,
                ),
            ))
        child_object.__dict__['_bound_children'] = tuple(bound_children)

        # Propagate visited relations for cycle detection in nested objects
        if hasattr(self, '_visited_relations'):
            child_object._visited_relations = self._visited_relations

        if not bind:
            child_object.request = None
            child_object.__dict__.pop('policy', None)

        return child_object

    def _row_address(self, instance: models.Model) -> str:
        return address.item(self.address, str(instance.pk))

    def _bind_relation_children(
        self,
        instances: Iterable[models.Model],
        *,
        owner_address: str,
    ) -> tuple[BoundGlueChild, ...]:
        """Bind the collection's projected-relation children, one shared child
        per unique related object (state-model.md §4: "The collection owns
        relation children; rows hold address references").

        Two rows referencing the same related object resolve to one address
        and one proxy, because the canonical address is derived from the
        collection's own address plus the related object's key -- never from
        the introducing row. The collection therefore owns these children and
        its disposal cascades to them, independent of any single row. A row
        with a `None` related object (nullable relation) contributes no child.
        """
        children: dict[tuple[str, Any], BoundGlueChild] = {}
        for relation_name, subfields in self._projected_relations:
            for instance in instances:
                if self._relation_is_to_many(relation_name):
                    related = self._related_queryset(instance, relation_name)
                    related_key = instance.pk
                else:
                    related = getattr(instance, relation_name)
                    related_key = getattr(related, 'pk', None)
                if related is None:
                    continue
                member = (relation_name, related_key)
                if member in children:
                    continue
                child = self._construct_relation_child(
                    related,
                    owner=instance,
                    relation_name=relation_name,
                    name=f'{self.name}.{relation_name}.{related_key}',
                    subfields=subfields,
                )
                if not child.is_authorized(
                    self.request,
                    GlueOperation(
                        kind=GlueOperationKind.INTRODUCE,
                        attribute=None,
                        required_access=child.access,
                    ),
                ):
                    continue
                child.request = self.request
                children[member] = BoundGlueChild(
                    path=f'{relation_name}.{related_key}',
                    address=self._relation_child_address(
                        owner_address,
                        relation_name,
                        related_key,
                    ),
                    glue_object=child,
                )
        return tuple(children.values())

    @staticmethod
    def _relation_child_address(
        owner_address: str,
        relation_name: str,
        related_pk: Any,
    ) -> str:
        """Canonical address of a collection-owned relation child.

        The raw relation path and the related object's key sit beneath the
        collection's own address, so the same related object yields the same
        address no matter which row introduced it.
        """
        return address.child(owner_address, f'{relation_name}:{related_pk}')
