from __future__ import annotations

import hashlib
import pickle
from dataclasses import dataclass
from typing import Any, Sequence, TypedDict, TypeVar, cast

from django.core.exceptions import FieldDoesNotExist, FieldError
from django.db.models import Model, Q, QuerySet

from django_glue.glue.options.django.constants import (
    DEFAULT_EXCLUDED_MODEL_FIELD_TYPES,
    DEFAULT_SEARCH_LIMIT,
    QUERYSET_CHOICE_OPTIONS_ATTRIBUTE,
)

ChoiceSource = TypeVar('ChoiceSource')


@dataclass(frozen=True)
class QuerySetChoiceOptions:
    search_fields: tuple[str, ...]
    fields: tuple[str, ...]
    search_limit: int


class RelatedModelChoicesResult(TypedDict):
    results: list[dict[str, Any]]


class GlueRelatedModelChoices:
    def __init__(
        self,
        queryset: QuerySet,
        *,
        value_field_name: str | None = None,
    ) -> None:
        _validate_queryset(queryset)
        self.queryset = queryset
        self.value_field_name = (
            value_field_name or queryset.model._meta.pk.name
        )

    @property
    def explicit_options(self) -> QuerySetChoiceOptions | None:
        return getattr(
            self.queryset.query,
            QUERYSET_CHOICE_OPTIONS_ATTRIBUTE,
            None,
        )

    @property
    def options(self) -> QuerySetChoiceOptions:
        return self.explicit_options or QuerySetChoiceOptions(
            search_fields=(),
            fields=(),
            search_limit=DEFAULT_SEARCH_LIMIT,
        )

    @property
    def is_searchable(self) -> bool:
        return bool(self.options.search_fields)

    def fingerprint(self) -> str:
        query = self.queryset.query.clone()
        if hasattr(query, QUERYSET_CHOICE_OPTIONS_ATTRIBUTE):
            delattr(query, QUERYSET_CHOICE_OPTIONS_ATTRIBUTE)

        fingerprint_value = (
            query,
            self.options,
            self.value_field_name,
        )
        return hashlib.sha256(pickle.dumps(fingerprint_value)).hexdigest()[:32]

    def serialize_item(self, instance: Model) -> dict[str, Any]:
        label = str(instance)
        choice_object = {
            'pk': instance.pk,
            '__str__': label,
        }
        for field_name in self.options.fields:
            choice_object[field_name] = getattr(instance, field_name)
        return {
            'value': instance.serializable_value(self.value_field_name),
            'label': label,
            'obj': choice_object,
        }

    def serialize_selected_values(
        self,
        values: Sequence[Any],
    ) -> list[dict[str, Any]]:
        if not values:
            return []

        queryset = self.queryset.filter(
            **{f'{self.value_field_name}__in': values}
        )
        choices_by_value = {
            str(choice['value']): choice
            for choice in (
                self.serialize_item(instance)
                for instance in queryset
            )
        }
        return [
            choices_by_value[str(value)]
            for value in values
            if str(value) in choices_by_value
        ]

    def load(self, *, search: str = '') -> RelatedModelChoicesResult:
        queryset = self.queryset
        if self.is_searchable:
            if not search:
                return self.empty()

            search_filter = Q()
            for search_field in self.options.search_fields:
                search_filter |= Q(**{f'{search_field}__icontains': search})
            queryset = queryset.filter(search_filter)
            if not queryset.ordered:
                queryset = queryset.order_by(queryset.model._meta.pk.name)
            queryset = queryset[:self.options.search_limit]

        return {
            'results': [self.serialize_item(instance) for instance in queryset],
        }

    @staticmethod
    def empty() -> RelatedModelChoicesResult:
        return {'results': []}


def configure_choices(
    source: ChoiceSource,
    *,
    search_fields: Sequence[str] = (),
    fields: Sequence[str] = (),
    search_limit: int = DEFAULT_SEARCH_LIMIT,
) -> ChoiceSource:
    if not isinstance(source, QuerySet):
        if search_fields or fields or search_limit != DEFAULT_SEARCH_LIMIT:
            msg = (
                'search_fields, fields, and search_limit are only supported '
                'for Django QuerySet choice sources.'
            )
            raise TypeError(msg)
        return source

    _validate_queryset(source)
    _validate_search_limit(search_limit)
    configured_queryset = source.all()
    if search_fields and configured_queryset.query.is_sliced:
        msg = 'Searchable Glue.choices querysets must not be sliced.'
        raise ValueError(msg)
    normalized_search_fields = _normalize_search_fields(
        queryset=configured_queryset,
        search_fields=search_fields,
    )
    setattr(
        configured_queryset.query,
        QUERYSET_CHOICE_OPTIONS_ATTRIBUTE,
        QuerySetChoiceOptions(
            search_fields=normalized_search_fields,
            fields=_normalize_fields(
                queryset=configured_queryset,
                fields=fields,
            ),
            search_limit=search_limit,
        ),
    )
    return cast('ChoiceSource', configured_queryset)


def _validate_queryset(queryset: QuerySet) -> None:
    if not isinstance(queryset, QuerySet):
        msg = 'Related model choices require a Django QuerySet.'
        raise TypeError(msg)


def _validate_search_limit(search_limit: int) -> None:
    if isinstance(search_limit, bool) or not isinstance(search_limit, int) or search_limit < 1:
        msg = f'Glue.choices search_limit must be a positive integer, got {search_limit!r}.'
        raise ValueError(msg)


def _normalize_search_fields(
    queryset: QuerySet,
    search_fields: Sequence[str],
) -> tuple[str, ...]:
    if isinstance(search_fields, str):
        msg = 'Glue.choices search_fields must be a sequence of field names, not a string.'
        raise TypeError(msg)

    normalized = []
    for search_field in search_fields:
        if not isinstance(search_field, str) or not search_field:
            msg = 'Glue.choices search_fields must contain non-empty strings.'
            raise TypeError(msg)
        if search_field in normalized:
            continue
        if search_field not in queryset.query.annotations:
            try:
                field = queryset.model._meta.get_field(search_field)
            except FieldDoesNotExist as exception:
                msg = f'Glue.choices received an invalid search field: {search_field!r}.'
                raise ValueError(msg) from exception
            if field.is_relation:
                msg = f'Glue.choices search field {search_field!r} must not be a relation.'
                raise ValueError(msg)
        try:
            queryset.filter(**{f'{search_field}__icontains': ''})
        except FieldError as exception:
            msg = f'Glue.choices received an invalid search field: {search_field!r}.'
            raise ValueError(msg) from exception
        normalized.append(search_field)
    return tuple(normalized)


def _normalize_fields(
    queryset: QuerySet,
    fields: Sequence[str],
) -> tuple[str, ...]:
    if isinstance(fields, str):
        msg = 'Glue.choices fields must be a sequence, not a string.'
        raise TypeError(msg)

    normalized = []
    for field_name in fields:
        if not isinstance(field_name, str) or not field_name:
            msg = 'Glue.choices fields must contain non-empty strings.'
            raise TypeError(msg)
        if field_name in normalized:
            continue
        if field_name in {'pk', '__str__'}:
            msg = f'Glue.choices field name {field_name!r} is reserved.'
            raise ValueError(msg)
        if field_name in queryset.query.annotations:
            normalized.append(field_name)
            continue
        try:
            field = queryset.model._meta.get_field(field_name)
        except FieldDoesNotExist as exception:
            msg = f'Glue.choices received an invalid choice field: {field_name!r}.'
            raise ValueError(msg) from exception
        if field.is_relation:
            msg = f'Glue.choices choice field {field_name!r} must not be a relation.'
            raise ValueError(msg)
        if field.get_internal_type() in DEFAULT_EXCLUDED_MODEL_FIELD_TYPES:
            msg = f'Glue.choices choice field {field_name!r} cannot be serialized.'
            raise ValueError(msg)
        normalized.append(field_name)

    return tuple(normalized)
