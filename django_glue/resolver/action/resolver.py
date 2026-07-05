from django.http import HttpRequest, JsonResponse, HttpResponse
from django.conf import settings
from pydantic import ValidationError

from django_glue.resolver.resolver import BaseResolver
from django_glue.resolver.action.schemas import ActionRequest

class ActionResolver(BaseResolver):
    def __init__(self, request: HttpRequest, action: str, proxy_name: str) -> None:
        self.request = request
        self.action = action
        self.proxy_name = proxy_name

    def resolve(self) -> JsonResponse | HttpResponse:
        try:
            return ActionRequest.model_validate({'request': self.request}).process()
        except ValidationError as e:
            return HttpResponse(
                content=f'{e}' if settings.DEBUG else 'Malfunctioned Glue Request',
                status=400,
                content_type='text/plain',
            )


