from __future__ import annotations

import json
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from django.http import HttpRequest


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

