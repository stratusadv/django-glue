from typing import Literal

from pydantic import BaseModel


class GlueTemplatePolicyDetails(BaseModel):
    namespace: Literal['template']
    template_path: str
    initial_context_data: dict
