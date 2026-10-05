from __future__ import annotations

from collections.abc import Iterator, MutableMapping
from typing import TYPE_CHECKING, Any

from django.core.cache import cache

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
        self.request = request
        self.namespace = namespace
        self._key = f'{settings.DJANGO_GLUE_COMPONENT_SESSION_CACHE_PREFIX}{namespace}'
        self._data: dict[str, Any] | None = None
        self._dirty = False

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    def _load(self) -> dict[str, Any]:
        if self._data is None:
            loaded = cache.get(self._key)
            self._data = loaded if isinstance(loaded, dict) else {}
        return self._data

    def _require_string_key(self, key: Any) -> str:
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
            self._dirty = True
        data[key] = value

    def __delitem__(self, key: str) -> None:
        del self._load()[self._require_string_key(key)]
        self._dirty = True

    def __iter__(self) -> Iterator[str]:
        return iter(self._load())

    def __len__(self) -> int:
        return len(self._load())

    def save(self) -> None:
        """Write the namespace to the cache; a no-op unless it changed."""
        if not self._dirty:
            return
        cache.set(self._key, self._load())
        self._dirty = False

    def discard(self) -> None:
        """Delete the namespace's cache entry and forget the local view."""
        cache.delete(self._key)
        self._data = {}
        self._dirty = False
