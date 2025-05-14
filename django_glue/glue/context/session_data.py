from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django_glue.session.data import SessionData


@dataclass
class ContextGlueSessionData(SessionData):
    context_data: dict[str, Any]
    exclude: list[str] = field(default_factory=list)
    user_id: Any = None
