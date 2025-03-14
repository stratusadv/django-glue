from __future__ import annotations

from typing import TYPE_CHECKING

from django.core import serializers

if TYPE_CHECKING:
    from django.db.models import Model


def camel_to_snake(string: str) -> str:
    return ''.join(['_' + c.lower() if c.isupper() else c for c in string]).lstrip('_')


def serialize_object_to_json(model_object: Model) -> str:
    return serializers.serialize('json', [model_object, ])
