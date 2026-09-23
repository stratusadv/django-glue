from __future__ import annotations

import hashlib
import inspect
import pickle
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Sequence, TypedDict, TypeVar, cast

from django.core.exceptions import FieldDoesNotExist, FieldError
from django.db.models import Model, Q, QuerySet
from django.template import Context, Template
from django.template.response import TemplateResponse
from django.utils.module_loading import import_string

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.http import HttpRequest

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
    label_formatter: str | None = None


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
        self._label_formatter_takes_request: bool | None = None

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

    def serialize_item(self, instance: Model, request: HttpRequest) -> dict[str, Any]:
        label = self._render_label(instance, request)
        choice_object = {
            'pk': instance.pk,
            '__str__': str(instance),
        }
        for field_name in self.options.fields:
            choice_object[field_name] = getattr(instance, field_name)
        item = {
            'value': instance.serializable_value(self.value_field_name),
            'label': label,
            'obj': choice_object,
        }
        if self.options.label_formatter is not None:
            item['has_html_label'] = True
        return item

    def serialize_selected_values(
        self,
        values: Sequence[Any],
        request: HttpRequest,
    ) -> list[dict[str, Any]]:
        if not values:
            return []

        queryset = self.queryset.filter(
            **{f'{self.value_field_name}__in': values}
        )
        choices_by_value = {
            str(choice['value']): choice
            for choice in (
                self.serialize_item(instance, request)
                for instance in queryset
            )
        }
        return [
            choices_by_value[str(value)]
            for value in values
            if str(value) in choices_by_value
        ]

    def load(self, *, search: str = '', request: HttpRequest) -> RelatedModelChoicesResult:
        queryset = self.queryset
        if self.is_searchable:
            if search:
                search_filter = Q()
                for search_field in self.options.search_fields:
                    search_filter |= Q(**{f'{search_field}__icontains': search})
                queryset = queryset.filter(search_filter)
            if not queryset.ordered:
                queryset = queryset.order_by(queryset.model._meta.pk.name)
            queryset = queryset[:self.options.search_limit]

        return {
            'results': [
                self.serialize_item(instance, request) for instance in queryset
            ],
        }

    def _render_label(self, instance: Model, request: HttpRequest) -> str:
        if self.options.label_formatter is None:
            return str(instance)
        formatter = import_string(self.options.label_formatter)
        if self._label_formatter_takes_request is None:
            positional_count, has_var_positional = _label_formatter_positional_arity(
                formatter
            )
            self._label_formatter_takes_request = (
                has_var_positional or positional_count >= 2
            )
        if self._label_formatter_takes_request:
            result = formatter(request, instance)
        else:
            result = formatter(instance)
        if isinstance(result, TemplateResponse):
            result.render()
            return result.content.decode(result.charset or 'utf-8')
        if isinstance(result, str):
            return Template(result).render(Context())
        msg = (
            f'Glue.choices label_formatter {self.options.label_formatter!r} must return '
            f'a string or a TemplateResponse, got {type(result).__name__}.'
        )
        raise TypeError(msg)

    @staticmethod
    def empty() -> RelatedModelChoicesResult:
        return {'results': []}


def configure_choices(
    source: ChoiceSource,
    *,
    search_fields: Sequence[str] = (),
    fields: Sequence[str] = (),
    search_limit: int = DEFAULT_SEARCH_LIMIT,
    label_formatter: Callable | str | None = None,
) -> ChoiceSource:
    if not isinstance(source, QuerySet):
        if (
            search_fields
            or fields
            or search_limit != DEFAULT_SEARCH_LIMIT
            or label_formatter is not None
        ):
            msg = (
                'search_fields, fields, search_limit, and label_formatter are '
                'only supported for Django QuerySet choice sources.'
            )
            raise TypeError(msg)
        return source

    _validate_queryset(source)
    _validate_search_limit(search_limit)
    label_formatter_path = _normalize_label_formatter(label_formatter)
    configured_queryset = source.all()
    if not search_fields and fields:
        search_fields = fields
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
            label_formatter=label_formatter_path,
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


def _label_formatter_positional_arity(formatter: Callable) -> tuple[int, bool]:
    parameters = inspect.signature(formatter).parameters
    kinds = [parameter.kind for parameter in parameters.values()]
    positional_count = (
        kinds.count(inspect.Parameter.POSITIONAL_ONLY)
        + kinds.count(inspect.Parameter.POSITIONAL_OR_KEYWORD)
    )
    return positional_count, inspect.Parameter.VAR_POSITIONAL in kinds


def _normalize_label_formatter(label_formatter: Callable | str | None) -> str | None:
    """Resolve a label formatter to the dotted path that travels in the signed
    choice query. Only a string crosses the allowlisting unpickler; a callable
    must be importable back from its own path, so lambdas and closures fail."""
    if label_formatter is None:
        return None
    if isinstance(label_formatter, str):
        path = label_formatter
        try:
            resolved = import_string(path)
        except ImportError as exception:
            msg = f'Glue.choices label_formatter path {path!r} could not be imported.'
            raise ValueError(msg) from exception
        if not callable(resolved):
            msg = f'Glue.choices label_formatter path {path!r} does not resolve to a callable.'
            raise ValueError(msg)
    elif callable(label_formatter):
        resolved = label_formatter
        path = f'{label_formatter.__module__}.{label_formatter.__qualname__}'
        try:
            importable = import_string(path) is label_formatter
        except ImportError:
            importable = False
        if not importable:
            msg = (
                'Glue.choices label_formatter must be importable by its dotted path, '
                'since only the path travels inside glue policies -- use a '
                'module-level function or a dotted path string, not a lambda or closure.'
            )
            raise ValueError(msg)
    else:
        msg = 'Glue.choices label_formatter must be a callable or a dotted path string.'
        raise TypeError(msg)

    try:
        positional_count, has_var_positional = _label_formatter_positional_arity(resolved)
    except (TypeError, ValueError) as exception:
        msg = f'Glue.choices label_formatter {path!r} could not be inspected.'
        raise TypeError(msg) from exception
    if not has_var_positional and positional_count not in (1, 2):
        msg = (
            'Glue.choices label_formatter must accept (instance) or '
            '(request, instance).'
        )
        raise TypeError(msg)
    return path


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
