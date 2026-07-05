from django_glue.proxies.form.contract import GlueFormProxyContractData
from django_glue.proxies.model.contract import GlueModelProxyContractData


class GlueModelInstanceProxyContractData(GlueModelProxyContractData):
    target_pk: int | str | None
