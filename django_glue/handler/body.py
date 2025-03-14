import json
from typing import Any


class RequestBody:
    def __init__(self, django_request_body: bytes | str):
        self.data = json.loads(django_request_body.decode('utf-8'))
        self.unique_name = self.data['unique_name']
        self.action = self.data['action']

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def __setitem__(self, key: str, value: Any):
        self.data[key] = value
