from typing import Any, Literal

from pydantic import BaseModel, Field


class BaseGlueFormPolicyDetails(BaseModel):
    included_fields: dict[str, Any]
    form_class_path: str | None = Field(default=None, exclude_if=lambda value: value is None)
    target_pk: int | str | None # For ModelForms


class GlueFormPolicyDetails(BaseGlueFormPolicyDetails):
    namespace: Literal['form']
