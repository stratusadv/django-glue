from typing import Literal

from django_glue.proxies.model.policy import GlueModelPolicyDetails


class GlueModelInstancePolicyDetails(GlueModelPolicyDetails):
    namespace: Literal['model']

