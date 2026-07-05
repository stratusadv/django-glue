from django_glue.proxies.form.state import GlueFormProxyState


class GlueQuerySetProxyState(GlueFormProxyState):
    instance_pk: int | str | None
    list_data: list

