from __future__ import annotations

import base64
import json
import pickle
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from django.http import HttpRequest
    from django.db.models import QuerySet


def get_request_body_data(request: HttpRequest, key: str | None = None) -> dict:
    data = json.loads(request.body.decode('utf-8'))
    return data if key is None else data.get(key, None)


def get_inheritors(cls) -> set:
    subclasses = set()
    work = [cls]
    while work:
        parent = work.pop()
        for child in parent.__subclasses__():
            if child not in subclasses:
                subclasses.add(child)
                work.append(child)
    return subclasses


def get_class_from_path_string(class_path_string: str) -> Callable:
    module_path, class_name = class_path_string.rsplit('.', 1)
    import importlib  # noqa: PLC0415

    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def serialize_queryset(queryset: QuerySet) -> str:
    """Serialize a QuerySet query to a base64-encoded string."""
    return base64.b64encode(pickle.dumps(queryset.query)).decode()


def deserialize_queryset(encoded_query: str) -> QuerySet:
    """Reconstruct a QuerySet from a base64-encoded query string."""
    query = pickle.loads(base64.b64decode(encoded_query))
    queryset = query.model.objects.all()
    queryset.query = query
    return queryset
