from typing import Any

from pydantic import BaseModel


class GlueFormProxyContractData(BaseModel):
    allowed_fields: dict[str, Any]
    form_class_path: str | None = None
