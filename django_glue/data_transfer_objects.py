from pydantic import BaseModel


class GlueActionRequestData(BaseModel):
    action: str
    unique_name: str
    payload: dict | None = None


class GlueActionResponseData(BaseModel):
    data: dict
    success: bool
    message: str