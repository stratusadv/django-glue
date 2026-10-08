from __future__ import annotations

from collections.abc import Callable, Iterator, MutableMapping
from copy import deepcopy
from typing import TYPE_CHECKING, Any

from django_glue.conf import settings

if TYPE_CHECKING:
    from django.contrib.sessions.backends.base import SessionBase


class ComponentSession(MutableMapping[str, Any]):
    """
    Per-user, server-side scratch state for a component class (ADR 031).

    The mapping is one entry in the request's session, scoped by
    ``namespace`` under a prefixed key and shared by every instance of the
    component class within that user's session. Writes go straight into the
    session, and Django persists a modified session when the request
    completes; setting or deleting a key marks the session modified, so a
    request that writes nothing saves nothing. A value mutated in place is
    saved only once it is assigned back to its key. ``on_write`` is called
    with each key that is set or deleted. The session is not signed and never
    crosses the wire: it is not part of the policy token, static data, or
    computed data, and the client cannot read or write it.
    """

    def __init__(
        self,
        session: SessionBase,
        namespace: str,
        on_write: Callable[[str], None] | None = None,
    ) -> None:
        self._session = session
        self._on_write = on_write
        self._key = f'{settings.DJANGO_GLUE_COMPONENT_SESSION_KEY_PREFIX}{namespace}'

    def _load(self) -> dict[str, Any]:
        stored = self._session.get(self._key)
        return stored if isinstance(stored, dict) else {}

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
        data[key] = value
        self._session[self._key] = data
        if self._on_write is not None:
            self._on_write(key)

    def __delitem__(self, key: str) -> None:
        del self._load()[self._require_string_key(key)]
        self._session.modified = True
        if self._on_write is not None:
            self._on_write(key)

    def __iter__(self) -> Iterator[str]:
        return iter(self._load())

    def __len__(self) -> int:
        return len(self._load())


class SessionValue:
    """
    Storage for a declared attribute kept in its component's session
    (ADR 031), under the attribute's name. Reading a key that was never set
    returns the declared default without writing it, so a read never marks
    the session modified.
    """

    def __init__(
        self,
        default: Any = None,
        default_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.default = default
        self.default_factory = default_factory
        self.name = ''

    def __set_name__(self, owner: type, name: str) -> None:
        self.name = name

    def __get__(self, instance: Any, owner: type | None = None) -> Any:
        if instance is None:
            return self
        try:
            return instance.session[self.name]
        except KeyError:
            if self.default_factory is not None:
                return self.default_factory()
            return deepcopy(self.default)

    def __set__(self, instance: Any, value: Any) -> None:
        instance.session[self.name] = value

    def __delete__(self, instance: Any) -> None:
        instance.session.pop(self.name, None)
