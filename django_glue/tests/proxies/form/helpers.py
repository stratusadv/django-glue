from django_glue.access.access import GlueAccess
from django_glue.proxies.form.proxy import GlueFormProxy
from django_glue.proxies.form.state import GlueFormProxyState


def make_form_proxy(form, name='contact_form', access=GlueAccess.VIEW):
    return GlueFormProxy(
        name=name,
        namespace='form',
        access=access,
        state=GlueFormProxyState(form=form),
    )
