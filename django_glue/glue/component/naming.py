from __future__ import annotations

import datetime
import decimal
import hashlib
import uuid
from typing import Any

from django_glue.exceptions import GlueComponentKeyError

NAME_DIGEST_SIZE = 6

KEY_SAFE_TYPES = (
    str,
    int,
    bool,
    datetime.date,
    datetime.time,
    decimal.Decimal,
    uuid.UUID,
)


def canonical_key(value: Any) -> str:
    """Render a key as a type-preserving string.

    Glue canonicalizes the typed value rather than calling ``str()``, so integer
    ``1``, string ``'1'``, and the one-tuple ``(1,)`` cannot collide.
    """
    if value is None:
        return 'none'

    if isinstance(value, tuple):
        return '(' + ','.join(canonical_key(member) for member in value) + ')'

    if not isinstance(value, KEY_SAFE_TYPES):
        msg = (
            f'A component key must be an immutable scalar or a tuple of them, '
            f'not {type(value).__name__}. Mutable containers, Glue objects, '
            f'Django models, forms, and querysets are not keys.'
        )
        raise GlueComponentKeyError(msg)

    # bool is an int subclass, so it must be named before the int branch would
    # render True as 'int:True'.
    if isinstance(value, bool):
        return f'bool:{value}'

    if isinstance(value, datetime.datetime):
        return f'datetime:{value.isoformat()}'

    if isinstance(value, datetime.date):
        return f'date:{value.isoformat()}'

    if isinstance(value, datetime.time):
        return f'time:{value.isoformat()}'

    return f'{type(value).__name__}:{value}'


def derive_component_name(
    *,
    parent_name: str,
    tag_name: str,
    key: Any,
) -> str:
    """Derive a stamped component's stable, JavaScript-safe registration name.

    Deterministic in ``(parent_name, tag_name, key)`` and stable across renders
    for the same logical child, because the client registers proxies by name and
    a name that changes on every render creates a new proxy and defeats morph.

    The parent segment scopes keys to siblings: the same ``TimeEntryDay`` is
    unique by date under one dashboard but must not collide with another
    dashboard's identically dated card on the same page.

    This is a flat address. The derivation inputs match the addressing described
    in state-model.md; only the owner segment is folded into the digest rather
    than kept as a traversable path. See design/REINTEGRATION.md seam 5.
    """
    source = f'{parent_name}|{tag_name}|{canonical_key(key)}'
    digest = hashlib.blake2s(
        source.encode('utf-8'),
        digest_size=NAME_DIGEST_SIZE,
    ).hexdigest()

    return f'{_name_prefix(tag_name)}_{digest}'


def _name_prefix(tag_name: str) -> str:
    """A readable prefix so a name is debuggable in the client registry."""
    return tag_name.replace('-', '_').replace('.', '_')
