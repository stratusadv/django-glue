from typing import Any

from pydantic import BaseModel


class GlueFormProxyState(BaseModel):
    instance_data: dict[str, Any | None] | None = None
    errors: dict[str, Any | None] | None = None
