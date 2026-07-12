from typing import Literal

from pydantic import BaseModel


class GlueFunctionPolicyDetails(BaseModel):
    namespace: Literal['function']
    function_path: str
    params: list[dict]
