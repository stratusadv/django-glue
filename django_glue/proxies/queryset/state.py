from django_glue.proxies.form.state import GlueFormProxyState


class GlueQuerySetProxyState(GlueFormProxyState):
    instance_pk: int | str | None = None
    list_data: list | None = None

