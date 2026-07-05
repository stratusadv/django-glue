from django_glue.proxies.model.contract import GlueModelProxyContractData


class GlueQuerySetProxyContractData(GlueModelProxyContractData):
    encoded_queryset: str
