from __future__ import annotations

import base64
import json
import pickle
from collections import UserDict
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from django.http import HttpRequest
    from django.db.models import QuerySet


def get_request_body_data(request: HttpRequest, key: str | None = None) -> dict:
    data = json.loads(request.body.decode('utf-8'))
    return data if key is None else data.get(key, None)


def get_attr_from_path_string(class_path_string: str) -> Callable:
    module_path, class_name = class_path_string.rsplit('.', 1)
    import importlib  # noqa: PLC0415

    module = importlib.import_module(module_path)

    return getattr(module, class_name)


def get_attr_from_path_string_on_instance(instance: Any, path: str) -> Any:
    """Resolve a dotted path on an instance (e.g., 'services.increment_age_and_save')."""
    current = instance
    for part in path.split('.'):
        current = getattr(current, part, None)
        if current is None:
            return None
    return current



def serialize_queryset(queryset: QuerySet) -> str:
    """
    Serialize a QuerySet to a base64-encoded pickle string.

    Security note: This is safe because the serialized data is signed
    with HMAC-SHA256 as part of context_data. Any tampering with the
    encoded query will invalidate the signature and be rejected.
    """
    return base64.b64encode(pickle.dumps(queryset.query)).decode('utf-8')


def deserialize_queryset(encoded_query: str) -> QuerySet:
    """
    Reconstruct a QuerySet from a base64-encoded pickle string.

    Security note: This is safe because the encoded_query is verified
    via HMAC signature before reaching this point. Only server-generated
    queries can pass signature verification.
    """
    query = pickle.loads(base64.b64decode(encoded_query))
    queryset = query.model.objects.all()
    queryset.query = query
    return queryset

