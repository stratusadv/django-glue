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

    def __post_init__(self) -> None:
        self.messages = list(self.messages or [])

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
            html, _ = render_template_response_html(result)
            return cls(result=html)

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

    def to_payload(self, **extra: Any) -> dict[str, Any]:
        return {
            **extra,
            'result': self.result,
            'messages': [
                message.to_dict() for message in self.messages
            ],
        }

    def to_json_response(self, *, glue_object: Any = None, **extra: Any) -> JsonResponse:
        return JsonResponse(
            self._serialize_glue_values(self.to_payload(**extra), glue_object),
            status=self.status,
            safe=True,
            encoder=GlueResponseJSONEncoder,
        )

    @classmethod
    def _serialize_glue_values(cls, value: Any, glue_object: Any = None) -> Any:
        from django_glue.glue.base import BaseGlue

        if isinstance(value, BaseGlue):
            if glue_object is not None:
                value.request = glue_object.request
            return value.manifest.model_dump()

        if isinstance(value, dict):
            return {
                key: cls._serialize_glue_values(item, glue_object)
                for key, item in value.items()
            }

        if isinstance(value, list | tuple):
            return [
                cls._serialize_glue_values(item, glue_object)
                for item in value
            ]

        return value


class GlueRedirectResponse:
    def __new__(cls, view_name: str, **kwargs) -> GlueResponse:
        return GlueResponse(
            result={
                'redirect': {
                    'url': reverse(
                        view_name, kwargs=kwargs
                    )
                }
            }
        )


def render_template_response_html(
    response: TemplateResponse,
    request: HttpRequest | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """Render a TemplateResponse and collect the manifests registered on its request.

    Shared by GlueTemplateResponse.from_template_response (a `@Glue.attr`
    method returning a response directly) and GlueViewFragmentResolver's
    `Glue.view(...)` fragment resolution -- both need the same
    render + charset-safe decode + manifest-collection steps, just wrapped
    in different response envelopes for their respective transports.

    response.render() is a no-op if the response is already rendered, so
    this is safe to call regardless of caller-side render state.

    request identifies whose manifests to collect. Pass it explicitly when
    the caller already has the right request in hand -- e.g. the resolver
    passes its own self.request, which GlueContextManager treats as
    equivalent to the wrapped request it dispatched the view with (see
    test_glue_view_http_request_uses_base_request_for_registered_proxies).
    Falls back to response._request (set by Django's own TemplateResponse
    machinery during real rendering) when omitted, which is the common case
    for GlueTemplateResponse -- but that's a private attribute of a real
    TemplateResponse, so it's absent on some other HttpResponse subclasses
    and always absent on a mock, hence the explicit override.

    TODO: explore going further than sharing this one step -- GlueTemplateResponse's
    result envelope ({'is_glue_template_response': True, 'html', 'manifest_list'})
    and GlueViewFragmentResolver's bare {'html', 'manifest_list'} JsonResponse are
    still two independent shapes for what the client treats as the same kind of
    thing (see client_js/src/htmlResult.js vs. client_js/src/view.js -- both
    render HTML + ride-along manifests, with separate client classes). Worth
    checking whether Glue.view(...) could also return this same envelope shape
    (or GlueHtmlResult itself) so the client only needs one HTML-result type.
    """
    from django_glue.glue.context import GlueContextManager  # noqa: PLC0415

    response.render()

    resolved_request = request if request is not None else getattr(response, '_request', None)
    manifest_list = (
        GlueContextManager(resolved_request).serialized_manifests
        if resolved_request is not None
        else []
    )
    return response.content.decode(response.charset or 'utf-8'), manifest_list


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
    ride along as `manifest_list`, same as `Glue.view` does, so the client
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
        html, manifest_list = render_template_response_html(response)

        return GlueResponse(result={
            'is_glue_template_response': True,
            'html': html,
            'manifest_list': manifest_list,
        })
