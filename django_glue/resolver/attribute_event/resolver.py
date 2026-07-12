import inspect
from typing import Any, get_type_hints
from django.http import HttpRequest, JsonResponse, HttpResponse

from django_glue.exceptions import GlueAccessError
from django_glue.resolver.attribute_event.schemas import BoundProxyAttributeEvent
from django_glue.resolver.resolver import BaseResolver
from django_glue.response import GlueResponse
from django_glue.utils import get_attr_from_path_string_on_instance
from django_glue.proxies.proxy import BaseGlueProxy


class ProxyBoundAttributeEventResolver(BaseResolver):
    def __init__(self, bound_attribute_event: BoundProxyAttributeEvent) -> None:
        self.event = bound_attribute_event

    def _load_proxy_from_event(self) -> BaseGlueProxy:
        proxy_class: type[BaseGlueProxy] = self.event.policy.proxy_class
        return proxy_class._from_attribute_event(self.event)

    def _get_attribute_owner_from_event(self, proxy: BaseGlueProxy) -> Any:
        attribute_owner = proxy._get_bound_attribute_owner(
            self.event.bound_attribute
        )

        if not attribute_owner:
            msg = f'No valid attribute owner for {self.event.bound_attribute.target_class.__name__}'
            raise ValueError(msg)

        return attribute_owner

    def _resolve_attribute_on_owner(self, attribute_owner: Any, attr_name: str):
        """Resolve a dotted attribute path on the owner instance."""
        return get_attr_from_path_string_on_instance(attribute_owner, attr_name)

    def _build_kwargs(self, callable_attribute: Any) -> dict:
        """Merge event_kwargs with auto-injected request if the callable needs it."""
        kwargs = dict(self.event.event_kwargs or {})
        unwrapped = inspect.unwrap(callable_attribute)
        sig = inspect.signature(unwrapped)
        fn_globals = getattr(unwrapped, "__globals__", {})
        type_hints = get_type_hints(unwrapped, globalns={**fn_globals, "HttpRequest": HttpRequest})

        for param_name, param in sig.parameters.items():
            if param_name == 'self':
                continue
            hint = type_hints.get(param_name)
            if hint is not None and isinstance(hint, type) and issubclass(hint, HttpRequest):
                kwargs[param_name] = self.event.request
            elif param_name not in kwargs and param.default is not inspect.Parameter.empty:
                pass

        return kwargs

    def resolve(self) -> JsonResponse | HttpResponse:
        proxy = self._load_proxy_from_event()
        attribute_owner = self._get_attribute_owner_from_event(proxy)

        attr_name = self.event.bound_attribute.name

        if self.event.bound_attribute.is_callable:
            callable_attribute = self._resolve_attribute_on_owner(attribute_owner, attr_name)
            kwargs = self._build_kwargs(callable_attribute)
            try:
                result_data = callable_attribute(**kwargs)
            except GlueAccessError:
                raise
            except Exception as e:
                from django_glue.exceptions import GlueBoundAttributeCallError  # noqa: PLC0415
                raise GlueBoundAttributeCallError(
                    callable_attribute, e, list(kwargs.keys())
                ) from e
        else:
            result_data = self._resolve_attribute_on_owner(attribute_owner, attr_name)

        state_dict = proxy.state.serialize()

        if isinstance(result_data, GlueResponse):
            result_data.state = state_dict
            return result_data.to_json_response()

        return GlueResponse(
            state=state_dict,
            result=result_data,
        ).to_json_response()
