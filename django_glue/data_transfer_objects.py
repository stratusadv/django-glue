from pydantic import BaseModel


class GlueActionRequestData(BaseModel):
    context_data: dict
    payload: dict | None = None


class GlueActionResponseData(BaseModel):
    data: dict
    success: bool
    message: str