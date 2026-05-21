from django.http import HttpRequest, JsonResponse, HttpResponse

from django_glue.resolver.action.encoders import ActionDataJSONEncoder
from django_glue.maps import SUBJECT_TYPE_TO_PROXY_TYPE
from django_glue.resolver.resolver import BaseResolver
from django_glue.resolver.action.schemas import ActionPayloadSchema
from django_glue.session import GlueSession


class ActionResolver(BaseResolver):
    def __init__(self, request: HttpRequest, action: str, unique_name: str) -> None:
        self.request = request
        self.action = action
        self.unique_name = unique_name

    def resolve(self) -> JsonResponse | HttpResponse:
        if self.request.content_type not in ['application/json', 'multipart/form-data']:
            return HttpResponse(
                content=f'Unsupported media type {self.request.content_type}',
                status=400,
                content_type='text/plain',
            )

        action_payload = ActionPayloadSchema.from_request(self.request)

        proxy_access = GlueSession(self.request).get_proxy_access(self.unique_name)

        proxy_instance = SUBJECT_TYPE_TO_PROXY_TYPE[
            action_payload.context_data['subject_type']
        ].from_action_request_data(
            access=proxy_access, unique_name=self.unique_name, **action_payload.context_data
        )

        action_response_data = proxy_instance.process_action(self.action, action_payload)

        return JsonResponse(
            data=action_response_data, safe=False, encoder=ActionDataJSONEncoder
        )
