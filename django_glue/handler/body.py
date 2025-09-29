import json
from typing import Any

from django.http import HttpRequest

from django_glue.constants import UNIQUE_NAME_KEY, ACTION_KEY
from django_glue.session import Session


class GlueRequest:
    def __init__(self, django_request: HttpRequest):
        self.data = json.loads(django_request.body.decode('utf-8'))
        self.session = Session(django_request)
        self.unique_name = self.data[UNIQUE_NAME_KEY]
        self.action = self.data[ACTION_KEY]

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def __setitem__(self, key: str, value: Any):
        self.data[key] = value
