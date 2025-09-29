from typing import Any

from pydantic import BaseModel, field_validator, ValidationError

from django_glue.glue.enums import GlueType


class GlueRequestData(BaseModel):
    unique_name: str
    type: str
    action: str
    action_kwargs: dict[str, Any]

    @field_validator('type', mode='before')
    @classmethod
    def validate_type(cls, value: str):
        try:
            GlueType(value)
        except ValueError:
            raise ValidationError(f'Invalid glue type {value} in request data')

        return value

    @field_validator('action', mode='after')
    @classmethod
    def validate_action(cls, value: str):
        glue_type = GlueType(value)

        try:
            glue_type.action_type(value)
        except:
            raise ValidationError(f'Invalid action {value} for glue type {value} in request data')

        return value

