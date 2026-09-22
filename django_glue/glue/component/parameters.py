from __future__ import annotations

import datetime
import decimal
import types
import uuid
from typing import Any, get_args, get_origin, get_type_hints, Union

from django_glue.exceptions import GlueComponentParameterError

_NONE_TYPE = type(None)


def _coerce_date(value: Any) -> datetime.date:
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    return datetime.date.fromisoformat(value)


def _coerce_datetime(value: Any) -> datetime.datetime:
    if isinstance(value, datetime.datetime):
        return value
    return datetime.datetime.fromisoformat(value)


def _coerce_time(value: Any) -> datetime.time:
    if isinstance(value, datetime.time):
        return value
    return datetime.time.fromisoformat(value)


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {'true', '1', 'yes', 'on'}
    return bool(value)


# Every entry must round-trip through GlueResponseJSONEncoder: the parameter is
# signed into the policy as JSON and read back on reconstruction. A parameter
# whose annotation is absent from this table cannot survive that trip, so it is
# rejected at declaration rather than silently handed back as its decoded form.
PARAMETER_COERCIONS: dict[type, Any] = {
    bool: _coerce_bool,
    int: int,
    float: float,
    str: str,
    datetime.datetime: _coerce_datetime,
    datetime.date: _coerce_date,
    datetime.time: _coerce_time,
    decimal.Decimal: decimal.Decimal,
    uuid.UUID: uuid.UUID,
}


def unwrap_optional(annotation: Any) -> tuple[Any, bool]:
    """Return the non-None member of an optional annotation, and whether it was optional."""
    origin = get_origin(annotation)

    # `Optional[str]` resolves to typing.Union; `str | None` to types.UnionType.
    if origin is not Union and origin is not types.UnionType:
        return annotation, False

    members = [arg for arg in get_args(annotation) if arg is not _NONE_TYPE]

    if len(members) != 1:
        return annotation, _NONE_TYPE in get_args(annotation)

    return members[0], _NONE_TYPE in get_args(annotation)


def resolve_parameter_annotations(
    owner: type,
    parameter_names: tuple[str, ...],
) -> dict[str, Any]:
    """Resolve and validate the declared annotation for each parameter.

    Raises when a parameter is unannotated or annotated with a type that cannot
    round-trip through the signed policy.
    """
    try:
        hints = get_type_hints(owner)
    except Exception as error:
        msg = (
            f'{owner.__name__} has parameter annotations that cannot be resolved: {error}. '
            f'Every Glue.attr(parameter=True) declaration needs a resolvable type annotation.'
        )
        raise GlueComponentParameterError(msg) from error

    annotations: dict[str, Any] = {}

    for name in parameter_names:
        if name not in hints:
            msg = (
                f"Parameter '{name}' on {owner.__name__} has no type annotation. "
                f'A parameter is coerced back to its annotation on reconstruction, '
                f'so the annotation is required.'
            )
            raise GlueComponentParameterError(msg)

        annotation, _ = unwrap_optional(hints[name])

        if annotation not in PARAMETER_COERCIONS:
            supported = ', '.join(sorted(item.__name__ for item in PARAMETER_COERCIONS))
            msg = (
                f"Parameter '{name}' on {owner.__name__} is annotated {annotation!r}, "
                f'which cannot round-trip through a signed policy. Supported: {supported}.'
            )
            raise GlueComponentParameterError(msg)

        annotations[name] = hints[name]

    return annotations


def coerce_parameter(name: str, value: Any, annotation: Any, owner_name: str) -> Any:
    """Coerce a decoded parameter value back to its declared annotation."""
    resolved, is_optional = unwrap_optional(annotation)

    if value is None:
        if is_optional:
            return None
        msg = f"Parameter '{name}' on {owner_name} is not optional but received None."
        raise GlueComponentParameterError(msg)

    coercion = PARAMETER_COERCIONS[resolved]

    try:
        return coercion(value)
    except (TypeError, ValueError) as error:
        msg = (
            f"Parameter '{name}' on {owner_name} could not be coerced to "
            f'{resolved.__name__} from {value!r}: {error}'
        )
        raise GlueComponentParameterError(msg) from error
