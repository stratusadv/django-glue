from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django_glue.access import GlueAccess


class GlueOperationKind(StrEnum):
    INTRODUCE = 'introduce'
    REFRESH = 'refresh'
    UPDATE = 'update'
    CALL = 'call'


@dataclass(frozen=True, slots=True, kw_only=True)
class GlueOperation:
    kind: GlueOperationKind
    attribute: str | None
    required_access: GlueAccess
