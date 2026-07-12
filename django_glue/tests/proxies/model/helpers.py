from django_glue.access.access import GlueAccess
from django_glue.proxies.model.instance.proxy import GlueModelInstanceProxy


def make_model_proxy(model, name='gorilla', access=GlueAccess.VIEW, fields=(), exclude=(), form_class=None):
    state, form_class_path = GlueModelInstanceProxy._build_state(
        model,
        fields=fields,
        exclude=exclude,
        form_class=form_class,
    )
    proxy = GlueModelInstanceProxy(name=name, namespace='model', access=access, state=state)
    proxy._form_class_path = form_class_path
    return proxy
