import json
from typing import Any
from urllib.parse import parse_qs, urlparse

from django.http import HttpRequest, QueryDict


class ViewFragmentHttpRequest:
    """Wraps an HttpRequest, overriding select attributes for a target view call."""

    def __init__(
        self, base_request: HttpRequest, method: str, url_path: str, view_payload: dict
    ) -> None:
        self._base = base_request
        self.method = method
        self.body = json.dumps(view_payload).encode('utf-8')
        self.content_type = 'application/json'

        parsed = urlparse(url_path)
        self.path_info = parsed.path

        query_params = parse_qs(parsed.query, keep_blank_values=True)
        query_dict = {}

        for key, values in query_params.items():
            query_dict[key] = values[0] if len(values) == 1 else values
        self.GET = QueryDict(mutable=True)

        for key, value in query_dict.items():
            self.GET[key] = value

    def __getattr__(self, name: str) -> Any:
        return getattr(self._base, name)

    @property
    def glue_context_request(self) -> HttpRequest:
        return self._base
