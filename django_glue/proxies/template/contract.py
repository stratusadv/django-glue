from pydantic import BaseModel


class GlueTemplateProxyContractData(BaseModel):
    template_path: str
    initial_context_data: dict
