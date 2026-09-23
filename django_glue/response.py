from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Iterable, Self

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.template.response import TemplateResponse
from django.urls import reverse

from django_glue.encoders import GlueResponseJSONEncoder
from django_glue.exceptions import GlueError
from django_glue.message import GlueMessage


@dataclass
class GlueResponse:
    Message: ClassVar[type] = GlueMessage

    result: Any = None
    messages: Iterable[GlueMessage] | None = None
    status: int = 200
    redirect: dict[str, Any] | None = None
    dispose: Iterable[str] | None = None
    html: str | None = None
    objects: list[dict[str, Any]] | None = None

    def __post_init__(self) -> None:
        self.messages = list(self.messages or [])
        self.dispose = list(self.dispose or [])
        self.objects = list(self.objects or [])

    @classmethod
    def from_result(cls, result: Any, *, render_as_html: bool = False) -> Self:
        if isinstance(result, cls):
            return result

        if isinstance(result, TemplateResponse):
            if render_as_html:
                # GlueTemplateResponse.from_template_response always returns
                # a plain GlueResponse, not cls -- correct here since
                # from_result is only ever actually called as
                # GlueResponse.from_result (see BaseGlue.process_attribute_call),
                # never on a GlueResponse subclass, so cls is always
                # GlueResponse in practice. Cast rather than widen the return
                # type for every other caller.
                return GlueTemplateResponse.from_template_response(result)  # type: ignore[return-value]

            # Without render_as_html=True (set via @Glue.attr(render_as_html=True)
            # or the Glue.html_attr shortcut), a TemplateResponse is just
            # rendered to text and sent as plain result data -- no implicit
            # GlueTemplateResponse envelope.
            return cls(result=render_html_payload(result)['html'])

        if isinstance(result, HttpResponse):
            msg = (
                f'Cannot coerce {type(result).__name__} returned from a Glue attribute -- '
                'only TemplateResponse (via GlueTemplateResponse.from_template_response) is '
                'supported. Render the response yourself and return its .content, or return '
                'a GlueTemplateResponse directly.'
            )
            raise TypeError(msg)

        return cls(result=result)

    @classmethod
    def from_error(cls, error: GlueError) -> Self:
        is_server_error = error.status >= 500
        expose_details = settings.DEBUG or not is_server_error

        return cls(
            result={
                'error': {
                    'code': error.code,
                    'message': (
                        str(error)
                        if expose_details
                        else 'An unexpected Glue server error occurred.'
                    ),
                    'status': error.status,
                    'details': error.details() if expose_details else {},
                }
            },
            status=error.status,
        )

    def to_json_response(self) -> JsonResponse:
        return JsonResponse(
            {
                'result': self.result,
                'messages': [
                    message.to_dict() for message in self.messages
                ],
            },
            status=self.status,
            safe=True,
            encoder=GlueResponseJSONEncoder,
        )

    @classmethod
    def _reject_glue_objects(cls, value: Any, *, path: str = 'result') -> None:
        from django_glue.glue.base import BaseGlue

        if isinstance(value, BaseGlue):
            message = (
                f'BaseGlue value of type {type(value).__name__} cannot appear '
                f'nested at {path}; return it directly as the result instead.'
            )
            raise TypeError(message)

        if isinstance(value, dict):
            for key, item in value.items():
                cls._reject_glue_objects(item, path=f'{path}.{key}')
        elif isinstance(value, list | tuple):
            for index, item in enumerate(value):
                cls._reject_glue_objects(item, path=f'{path}[{index}]')


class GlueRedirectResponse:
    def __new__(cls, view_name: str, **kwargs) -> GlueResponse:
        return GlueResponse(
            redirect={
                'url': reverse(
                    view_name, kwargs=kwargs
                )
            }
        )


def render_html_payload(
    response: HttpResponse,
    request: HttpRequest | None = None,
) -> dict[str, Any]:
    from django_glue.glue.context import GlueContextManager

    if isinstance(response, TemplateResponse):
        response.render()

    resolved_request = request if request is not None else getattr(response, '_request', None)
    objects = (
        GlueContextManager(resolved_request).serialized_objects
        if resolved_request is not None
        else []
    )
    return {
        'html': response.content.decode(response.charset or 'utf-8'),
        'objects': objects,
    }


class GlueTemplateResponse:
    """Render a template and return it from a `@Glue.attr` method as HTML.

    On the client, calling an attribute that returns one of these resolves
    to a chainable result instead of plain JSON data:

        const result = await Glue.namespace.proxyName.some_custom_thing()
        await result.renderInnerHtml('#target')

    Mirrors `Glue.view(...).renderInnerHtml(...)`, but the template renders
    inline against the *current* request/glue context (no second URL
    dispatch): it's given `request=` explicitly so request-context template
    tags (`{% csrf_token %}`, `{{ perms.* }}`, `{% render_static_modals %}`)
    work, and any `Glue.queryset()`/`Glue.model()`/etc. calls made earlier
    in the same request -- including by the rendered template itself --
    ride along as addressed `objects`, same as `Glue.view` does, so the client
    gets live proxies for anything new the render touched.
    """

    def __new__(
        cls,
        request: HttpRequest,
        template: str,
        context: dict[str, Any] | None = None,
    ) -> GlueResponse:
        return cls.from_template_response(TemplateResponse(request, template, context or {}))

    @classmethod
    def from_template_response(cls, response: TemplateResponse) -> GlueResponse:
        payload = render_html_payload(response)
        return GlueResponse(html=payload['html'], objects=payload['objects'])
