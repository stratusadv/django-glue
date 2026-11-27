from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import suppress
from dataclasses import fields, is_dataclass
from typing import Any

from django.core.files.base import File
from django.core.files.uploadedfile import UploadedFile
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Model, QuerySet
from django.db.models.fields.files import FieldFile
from pydantic import BaseModel


def is_dataclass_instance(value: Any) -> bool:
    """True for a dataclass instance, never a dataclass type."""
    return is_dataclass(value) and not isinstance(value, type)


def iter_nested_values(
    value: Any,
    *,
    path: str = '',
    visited: set[int] | None = None,
) -> Iterator[tuple[str, Any]]:
    """
    Yield ``(path, item)`` for ``value`` and every nested container or
    dataclass member, breaking reference cycles.
    """
    seen = visited if visited is not None else set()
    yield path, value

    value_is_dataclass = is_dataclass_instance(value)
    if not value_is_dataclass and not isinstance(value, Mapping | list | tuple | set | frozenset):
        return
    if id(value) in seen:
        return
    seen.add(id(value))

    if value_is_dataclass:
        for dataclass_field in fields(value):
            child_path = f'{path}.{dataclass_field.name}' if path else dataclass_field.name
            yield from iter_nested_values(
                getattr(value, dataclass_field.name),
                path=child_path,
                visited=seen,
            )
    elif isinstance(value, Mapping):
        for key, item in value.items():
            key_path = f'{path}.<key>' if path else '<key>'
            yield from iter_nested_values(key, path=key_path, visited=seen)
            item_path = f'{path}.{key}' if path else str(key)
            yield from iter_nested_values(item, path=item_path, visited=seen)
    else:
        for index, item in enumerate(value):
            yield from iter_nested_values(
                item,
                path=f'{path}[{index}]',
                visited=seen,
            )


def _serialize_field_file(file: FieldFile) -> dict | None:
    """Serialize a FieldFile (model file field) to a dict."""
    if not file:
        return None

    result = {'name': file.name}

    with suppress(ValueError):
        result['url'] = file.url

    return result


def _serialize_uploaded_file(file: UploadedFile) -> dict:
    """Serialize an UploadedFile (form submission) to a dict."""
    return {'name': file.name}


class GlueResponseJSONEncoder(DjangoJSONEncoder):
    def default(self, o: Any) -> Any:  # noqa: PLR0911
        if isinstance(o, BaseModel):
            return o.model_dump()

        if isinstance(o, Model | QuerySet):
            message = (
                f'Raw Django object {type(o).__name__} is not serializable as an '
                'ordinary Glue value.'
            )
            raise TypeError(message)

        if isinstance(o, FieldFile):
            return _serialize_field_file(o)

        if isinstance(o, UploadedFile):
            return _serialize_uploaded_file(o)

        if isinstance(o, File):
            return {'name': o.name}

        # Handle memoryview objects (returned by PostgreSQL for BinaryField)
        if isinstance(o, memoryview):
            return o.tobytes().decode('utf-8', errors='replace')

        # Handle bytes objects
        if isinstance(o, bytes):
            return o.decode('utf-8', errors='replace')

        if is_dataclass_instance(o):
            from django_glue.message import GlueMessage  # noqa: PLC0415
            from django_glue.response import GlueResponse  # noqa: PLC0415

            if isinstance(o, GlueResponse | GlueMessage):
                message = (
                    f'Internal Glue object {type(o).__name__} is not serializable '
                    'as an ordinary Glue value.'
                )
                raise TypeError(message)

            return {
                dataclass_field.name: getattr(o, dataclass_field.name)
                for dataclass_field in fields(o)
            }

        # For other types not handled by the default encoder,
        # delegate to the base class (which handles datetime, date, etc.)
        return super().default(o)
