from __future__ import annotations

import json

from django.http import JsonResponse
from typing_extensions import TYPE_CHECKING

from django.template.response import TemplateResponse


if TYPE_CHECKING:
    from django.core.handlers.wsgi import WSGIRequest


def showcase_view(request: WSGIRequest) -> TemplateResponse:
    return TemplateResponse(
        request,
        context={},
        template='developer/field/page/showcase_page.html'
    )


def input_field_view(request: WSGIRequest) -> TemplateResponse:
    return TemplateResponse(
        request,
        context={},
        template='developer/field/page/input_field_page.html'
    )


def endpoint_testing_view(request: WSGIRequest) -> JsonResponse:
    print('hit endpoint!')
    # print(json.loads(request.body))
    # print(request.GET)
    # print(request.POST)
    return JsonResponse(
        data={}
    )
