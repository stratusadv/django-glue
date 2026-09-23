from __future__ import annotations

import datetime
import decimal
import hashlib
import uuid
from typing import Any

from django_glue.exceptions import GlueComponentKeyError


KEY_SAFE_TYPES = (str, int, bool, datetime.date, datetime.time, decimal.Decimal, uuid.UUID)


def canonical_key(value: Any) -> str:
    if value is None:
        return 'none'
    if isinstance(value, tuple):
        if not value:
            raise GlueComponentKeyError('A component key tuple cannot be empty.')
        return '(' + ','.join(canonical_key(member) for member in value) + ')'
    if not isinstance(value, KEY_SAFE_TYPES):
        raise GlueComponentKeyError(
            f'A component key must be an immutable scalar or tuple, not {type(value).__name__}.'
        )
    if isinstance(value, bool):
        return f'bool:{value}'
    if isinstance(value, (datetime.date, datetime.time)):
        return f'{type(value).__name__}:{value.isoformat()}'
    return f'{type(value).__name__}:{value}'


def component_name(parent_address: str, tag_name: str, key: Any) -> str:
    source = f'{parent_address}|{tag_name}|{canonical_key(key)}'
    digest = hashlib.blake2s(source.encode(), digest_size=8).hexdigest()
    return f'{tag_name.replace("-", "_").replace(".", "_")}_{digest}'
