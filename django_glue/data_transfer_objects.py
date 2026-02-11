from pydantic import BaseModel


class GlueRequestData(BaseModel):
    action: str
    unique_name: str
    payload: dict | None = None


class GlueResponseData(BaseModel):
    data: dict
    success: bool
    message: str