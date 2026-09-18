"""Canonical addressed-object address construction (state-model.md §8, §10).

An address is a path of segments joined by separators. The top level carries an
opaque segment -- a digest of the object's namespace and name -- so equal names
registered in different apps do not collide. Every child segment is the raw
canonical path or member key, left readable. The wire treats an address as
opaque and never reparses the display spelling, so a client holds it as a token.
"""

from __future__ import annotations

from base64 import urlsafe_b64encode
from hashlib import sha256


def opaque_segment(namespace: str, name: str) -> str:
    """Return the opaque top-level segment for ``name`` in ``namespace``."""
    return urlsafe_b64encode(
        sha256(f'{namespace}\0{name}'.encode()).digest()[:12]
    ).decode().rstrip('=')


def top_level(name: str, namespace: str) -> str:
    """Address of a top-level introduced object: ``name#<opaque segment>``."""
    return f'{name}#{opaque_segment(namespace, name)}'


def child(owner_address: str, path: str) -> str:
    """Address of a named child or relation beneath its owner: ``owner.path``."""
    return f'{owner_address}.{path}'


def item(collection_address: str, key: str) -> str:
    """Address of a keyed collection item: ``collection[key]``."""
    return f'{collection_address}[{key}]'
