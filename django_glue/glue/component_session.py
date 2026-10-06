from __future__ import annotations

from collections.abc import Iterator, MutableMapping
from typing import TYPE_CHECKING, Any

from django_glue.conf import settings

if TYPE_CHECKING:
    from django.http import HttpRequest


class ComponentSession(MutableMapping[str, Any]):
    """Server-side scratch state for a component class (ADR 026).

    The mapping is one entry in the request's session, scoped by
    ``namespace`` under a prefixed key and shared by every instance of the
    component class within that user's session. Writes go straight into the
    session, and Django persists a modified session when the request
    completes; setting a key to a value it does not already hold marks the
    session modified, so a request that changes nothing saves nothing. The
    session is not signed and never crosses the wire: it is not part of the
    policy token, static data, or computed data, and the client cannot read
    or write it.
    """

    def __init__(self, request: HttpRequest, namespace: str) -> None:
        self.session = request.session
        self.namespace = namespace
        self._key = f'{settings.DJANGO_GLUE_COMPONENT_SESSION_KEY_PREFIX}{namespace}'

    @property
    def data(self) -> dict[str, Any]:
        return self._load()

    def _load(self) -> dict[str, Any]:
        stored = self.session.get(self._key)
        if not isinstance(stored, dict):
            stored = {}
            self.session[self._key] = stored
        return stored

    @staticmethod
    def _require_string_key(key: Any) -> str:
        if not isinstance(key, str):
            msg = f'ComponentSession keys must be strings, got {type(key).__name__}.'
            raise TypeError(msg)
        return key

    def __getitem__(self, key: str) -> Any:
        return self._load()[key]

    def __setitem__(self, key: str, value: Any) -> None:
        key = self._require_string_key(key)

        data = self._load()
        if key not in data or data[key] != value:
            self.set_modified()

        data[key] = value

    def __delitem__(self, key: str) -> None:
        del self._load()[self._require_string_key(key)]
        self.set_modified()

    def __iter__(self) -> Iterator[str]:
        return iter(self._load())

    def __len__(self) -> int:
        return len(self._load())

    def set_modified(self) -> None:
        self.session.modified = True
