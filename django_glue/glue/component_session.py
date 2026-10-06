from __future__ import annotations

from collections.abc import Iterator, MutableMapping
from typing import TYPE_CHECKING, Any

from django_glue.conf import settings

if TYPE_CHECKING:
    from django.http import HttpRequest


class ComponentSession(MutableMapping[str, Any]):
    """Server-side scratch state for a component class (ADR 026).

    The mapping is backed by one entry in the host application's default
    cache, scoped by ``namespace``. Setting a key to a value it does not
    already hold marks the namespace dirty, and the entry is written only when
    dirty. A ``Component`` flushes the session
    when its interaction completes, so ``save()`` is for code outside those
    points. The session is not signed and never crosses the wire: it is not
    part of the policy token, static data, or computed data, and the client
    cannot read or write it.
    """

    def __init__(self, request: HttpRequest, namespace: str) -> None:
        self.session = request.session
        self.namespace = namespace
        self._key = f'{settings.DJANGO_GLUE_COMPONENT_SESSION_CACHE_PREFIX}{namespace}'

    @property
    def data(self) -> dict[str, Any]:
        return self.session.get(self._key, {})

    @staticmethod
    def _require_string_key(key: Any) -> str:
        if not isinstance(key, str):
            msg = f'ComponentSession keys must be strings, got {type(key).__name__}.'
            raise TypeError(msg)
        return key

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        key = self._require_string_key(key)

        if key not in self.data or self.data[key] != value:
            self.set_modified()

        self.data[key] = value

    def __delitem__(self, key: str) -> None:
        del self.data[self._require_string_key(key)]
        self.set_modified()

    def __iter__(self) -> Iterator[str]:
        return iter(self.data)

    def __len__(self) -> int:
        return len(self.data)

    def set_modified(self) -> None:
        self.session.modified = True