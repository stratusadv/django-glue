import json
from typing import Any

from django_glue.constants import UNIQUE_NAME_KEY, ACTION_KEY


class RequestBody:
    def __init__(self, django_request_body: bytes | str):
        self.data = json.loads(django_request_body.decode('utf-8'))
        self.unique_name = self.data[UNIQUE_NAME_KEY]
        self.action = self.data[ACTION_KEY]

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def __setitem__(self, key: str, value: Any):
        self.data[key] = value
