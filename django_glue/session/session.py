from typing import Any

from django.http import HttpRequest


class BaseGlueSession:
    """
        Used to keep glue session data live for a set amount of time.
        Functionality to handle multiple windows/tabs.
    """
    _session_key: str = None

    def __init__(self, request: HttpRequest):
        self.request = request
        self.session = request.session.setdefault(self._session_key, dict())

    def __getitem__(self, key: str) -> Any:
        return self.session[key]

    def __setitem__(self, key: str, value: Any):
        self.session[key] = value

    def set_modified(self) -> None:
        self.request.session.modified = True