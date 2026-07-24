from __future__ import annotations

from typing import Any

from django_glue.glue.attributes.base import BaseGlueAttribute


class ReadableAttribute(BaseGlueAttribute):
    @property
    def metadata(self) -> dict[str, Any]:
        return super().metadata | {'namespace': 'readable'}

    @property
    def state(self) -> dict[str, Any]:
        return {'value': self.get()}
