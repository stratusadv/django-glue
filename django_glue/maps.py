from typing import Callable


# This is a nifty way we can define a set of default types to work with now, but still leave room
# for adding custom namespace and proxies later
class ProxyType:
    QUERY_SET = 'querySet'
    MODEL = 'model'
    FORM = 'form'
    TEMPLATE = 'template'
    FUNCTION = 'function'

    _registry: dict[str, type] = {}

    @classmethod
    def register(cls, namespace: str) -> Callable:
        def decorator(proxy_class: type) -> type:
            cls._registry[namespace] = proxy_class
            return proxy_class
        return decorator

    @classmethod
    def get_proxy_class(cls, namespace: str) -> type:
        if namespace not in cls._registry:
            msg = (
                f"Proxy type '{namespace}' is not registered. "
                f"Known types: {list(cls._registry.keys())}"
            )
            raise KeyError(
                msg
            )
        return cls._registry[namespace]

    @classmethod
    def get_namespaces(cls) -> list[str]:
        return list(cls._registry.keys())


def _register_builtins() -> None:
    from django_glue.proxies import (  # noqa: PLC0415
        GlueModelInstanceProxy,
        GlueFormProxy,
        GlueQuerySetProxy,
        GlueTemplateProxy,
        GlueFunctionProxy,
    )
    ProxyType._registry[ProxyType.QUERY_SET] = GlueQuerySetProxy
    ProxyType._registry[ProxyType.MODEL] = GlueModelInstanceProxy
    ProxyType._registry[ProxyType.FORM] = GlueFormProxy
    ProxyType._registry[ProxyType.TEMPLATE] = GlueTemplateProxy
    ProxyType._registry[ProxyType.FUNCTION] = GlueFunctionProxy


_register_builtins()
