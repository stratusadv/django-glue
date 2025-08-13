from __future__ import annotations

from typing_extensions import TYPE_CHECKING

from django.template.response import TemplateResponse

if TYPE_CHECKING:
    from django.core.handlers.wsgi import WSGIRequest


def session_data_view(request: WSGIRequest) -> TemplateResponse:
    """View that displays session data."""

    print(request.session)

    return TemplateResponse(
        request=request,
        context={'session_data': request.session},
        template='developer/page/session_data.html'
    )
