from typing import Literal

from django_glue.proxies.model.policy import GlueModelPolicyDetails


class GlueQuerySetPolicyDetails(GlueModelPolicyDetails):
    namespace: Literal['querySet']
    encoded_queryset: str
