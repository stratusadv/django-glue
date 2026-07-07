from pydantic import BaseModel


class GlueFunctionProxyContractData(BaseModel):
    function_path: str
    params: dict
