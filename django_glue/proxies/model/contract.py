from django_glue.proxies.form.contract import GlueFormProxyContractData


class GlueModelProxyContractData(GlueFormProxyContractData):
    pk_field_name: str
    model_class_path: str
