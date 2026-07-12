from django_glue.access.access import GlueAccess
from django_glue.proxies.queryset.proxy import GlueQuerySetProxy
from django_glue.proxies.queryset.state import GlueQuerySetProxyState


def make_queryset_proxy(queryset, name='gorillas', access=GlueAccess.VIEW, fields=(), exclude=(), form_class=None):
    model_instance = queryset.model()
    model_state, form_class_path = GlueQuerySetProxy._build_state(
        model_instance,
        fields=fields,
        exclude=exclude,
        form_class=form_class,
    )
    state = GlueQuerySetProxyState(
        queryset=queryset,
        model=model_state.model,
        form=model_state.form,
    )
    proxy = GlueQuerySetProxy(name=name, namespace='querySet', access=access, state=state)
    proxy._form_class_path = form_class_path
    return proxy
