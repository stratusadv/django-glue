from __future__ import annotations

import base64
import builtins
import pickle
from functools import cached_property
from typing import TYPE_CHECKING, Any, Literal, Mapping, Sequence

from django_glue.access import GlueAccess
from django_glue.conf import settings
from django_glue.exceptions import (
    GlueQuerySetFilterValidationError,
    GlueQuerySetSliceValidationError,
)
from django_glue.glue.attributes import BaseGlueAttribute, DeclaredAttribute
from django_glue.glue.base import BaseGlue
from django_glue.glue.loading import LoadingStrategy
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
    RelatedFieldConfig,
)
from django_glue.glue.objects.django.model_fields import ModelFieldResolutionMixin

if TYPE_CHECKING:
    from django import forms
    from django.db import models

    from django_glue.glue.policy import GluePolicy

DEFAULT_BATCH_SIZE = '__default__'


class QuerySetGlue(GlueComputedAttributesMixin, ModelGlueFormConfigMixin, ModelFieldResolutionMixin, BaseGlue):
    namespace = 'querySet'
    globally_excluded_field_types = ModelGlue.globally_excluded_field_types

    def __init__(
        self,
        queryset: models.QuerySet,
        *,
        name: str,
        access: GlueAccess,
        fields: Sequence[str] | Literal['__all__'] = (),
        exclude: Sequence[str] | Literal['__all__'] = (),
        form: forms.ModelForm | None = None,
        forms: Mapping[str, forms.ModelForm] | None = None,
        computed_attributes: Mapping[str, ComputedAttribute] | None = None,
        related_field_config: Mapping[str, RelatedFieldConfig] | None = None,
        loading_strategy: LoadingStrategy = LoadingStrategy.LAZY,
        batch_size: int | None | Literal['__default__'] = DEFAULT_BATCH_SIZE,
        last_query_params: dict[str, Any] | None = None,
        loaded_row_count: int = 0,
    ) -> None:
        super().__init__(name=name, access=access, loading_strategy=loading_strategy)
        self.queryset = queryset
        self.batch_size = self._resolve_batch_size(batch_size)
        self.fields = (
            fields if fields == ALL_FIELDS else tuple(fields)
        )
        self.exclude = (
            exclude if exclude == ALL_FIELDS else tuple(exclude)
        )

        if not self.fields and not self.exclude:
            msg = 'QuerySetGlue requires at least one of fields or exclude.'
            raise ValueError(msg)

        self.forms = self.normalize_forms(form, forms)
        self.related_field_config = ModelGlue._normalize_related_field_config(
            related_field_config=related_field_config,
            model_class=self.queryset.model,
        )
        self._select_related = self._get_select_related_fields()
        self.initialize_computed_attributes(computed_attributes)
        self._last_query_params = last_query_params
        self._loaded_row_count = loaded_row_count

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
            'model_class_path': f'{self.queryset.model.__module__}.{self.queryset.model.__name__}',
            'encoded_queryset': self._encode_queryset_query(self.queryset),
            'pk_field_name': self.queryset.model._meta.pk.name,
            'batch_size': self.batch_size,
            'last_query_params': self._last_query_params,
            'loaded_row_count': self._loaded_row_count,
        }
        if self.forms:
            identity['form_identities'] = self.serialize_forms(self.forms)
        if self.related_field_config:
            identity['related_field_config'] = ModelGlue._serialize_related_field_config(
                self.related_field_config
            )
        identity |= self.computed_attributes_identity()

        return identity

    def get_attribute_providers(self) -> dict[str, Any]:
        # Mirrors ModelGlue's {'instance': self.instance} -- a `@Glue.attr`
        # declared directly on the queryset's class (e.g. a custom
        # QuerySet subclass passed to `objects = MyQuerySet.as_manager()`)
        # is picked up automatically, bound to this exact, already-filtered
        # queryset instance as `self` inside the method.
        return {'queryset': self.queryset}

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

    @cached_property
    def attributes(self) -> dict[str, BaseGlueAttribute]:
        model_instance = self.queryset.model()
        model_object = ModelGlue(
            model_instance,
            name=f'{self.name}.__model__',
            access=self.access,
            fields=self._included_fields,
            annotations=self._orm_annotation_names,
            forms=self.forms,
            select_related=self._select_related,
            computed_attributes=self.computed_attributes,
            related_field_config=self.related_field_config,
        )
        # Get field attributes from the model, excluding model's declared attributes
        field_names = {
            *self._included_fields,
            *self._orm_annotation_names,
            *self._computed_attribute_names,
        }
        attributes: dict[str, BaseGlueAttribute] = {
            name: attribute
            for name, attribute in model_object.attributes.items()
            if name in field_names
        }
        # Add our own declared attributes
        attributes.update(super().attributes)
        return attributes

    def get_state(self) -> dict[str, Any]:
        return self._query()

    def get_metadata(self) -> dict[str, Any]:
        return {
            'attributes': {
                name: attribute.metadata
                for name, attribute in self.attributes.items()
            },
        }

    @cached_property
    def _orm_annotation_names(self) -> tuple[str, ...]:
        return tuple(self.queryset.query.annotations)

    @classmethod
    def _reconstruct_from_policy(cls, policy: GluePolicy) -> QuerySetGlue:
        queryset = cls._decode_queryset_query(policy.identity['encoded_queryset'])
        all_field_names = set(cls._all_available_field_names_for_meta(queryset.model._meta))
        fields = [
            attr
            for attr in policy.attributes
            if isinstance(attr, str) and attr in all_field_names
        ]
        forms = cls.deserialize_form_classes(
            policy.identity.get('form_identities', {})
        )
        glue_object = cls(
            queryset,
            name=policy.name,
            access=policy.access,
            fields=fields,
            forms=forms,
            computed_attributes=policy.identity.get('computed_attributes', {}),
            batch_size=policy.identity.get('batch_size'),
            last_query_params=policy.identity.get('last_query_params'),
            loaded_row_count=policy.identity.get('loaded_row_count', 0),
        )
        # Restored post-construction from the signed (already-validated) policy:
        # _deserialize_related_field_config yields the normalized internal shape,
        # so it does not go back through __init__ normalization.
        glue_object.related_field_config = ModelGlue._deserialize_related_field_config(
            policy.identity.get('related_field_config', {})
        )
        return glue_object

    @staticmethod
    def _encode_queryset_query(queryset: models.QuerySet) -> str:
        return base64.b64encode(pickle.dumps(queryset.query)).decode('utf-8')

    @staticmethod
    def _decode_queryset_query(encoded_query: str) -> models.QuerySet:
        query = pickle.loads(base64.b64decode(encoded_query))
        queryset = query.model.objects.all()
        queryset.query = query
        return queryset

    @DeclaredAttribute(required_access=GlueAccess.VIEW, updates_client_state=False)
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

    @DeclaredAttribute(required_access=GlueAccess.VIEW, updates_client_state=False)
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
            items = [self._build_child_model_payload(instance) for instance in objects]
            self._loaded_row_count += len(items)

            return {'items': items, 'seek_key': None, 'has_next': False, 'batch_size': None}

        cursor = GlueCollectionCursor(objects, self.batch_size)
        batch = cursor.seek(seek_key)
        self._loaded_row_count += len(batch.items)

        return {
            'items': [self._build_child_model_payload(instance) for instance in batch.items],
            'seek_key': batch.next_seek_key,
            'has_next': batch.has_next,
            'batch_size': self.batch_size,
        }

    @DeclaredAttribute(required_access=GlueAccess.VIEW, updates_client_state=False)
    def get(self, pk: Any) -> dict[str, Any]:
        return self._build_child_model_payload(self.queryset.get(pk=pk))

    @DeclaredAttribute(required_access=GlueAccess.VIEW, updates_client_state=False)
    def new(self, initial: dict | None = None) -> dict[str, Any]:
        instance = self.queryset.model(**initial) if initial else self.queryset.model()
        return self._build_child_model_payload(instance=instance)

    def _build_child_model_payload(self, instance: models.Model) -> dict[str, Any]:
        child_name = f'{self.policy.name}.{instance.pk}'
        child_forms = {
            # Need to rebuild the form here in order to properly bind instance data!
            name: form.__class__(instance=instance)
            for name, form in self.forms.items()
        }
        # Child models in query results are always eager - they contain the fetched data
        child_object = ModelGlue(
            instance,
            name=child_name,
            access=self.policy.access,
            fields=self._included_fields,
            annotations=self._orm_annotation_names,
            forms=child_forms,
            select_related=self._select_related,
            computed_attributes=self.computed_attributes,
            related_field_config=self.related_field_config,
            loading_strategy=LoadingStrategy.EAGER,
        )
        child_object.request = self.request

        # Propagate visited relations for cycle detection in nested objects
        if hasattr(self, '_visited_relations'):
            child_object._visited_relations = self._visited_relations

        return child_object.manifest.model_dump()
