from django.http import HttpRequest, JsonResponse, HttpResponse

from django_glue.resolver.action.encoders import ActionDataJSONEncoder
from django_glue.maps import SUBJECT_TYPE_TO_PROXY_TYPE
from django_glue.resolver.resolver import BaseResolver
from django_glue.resolver.action.schemas import ActionPayloadSchema
from django_glue.response import GlueJsonResponse
from django_glue.session import GlueSession


class ActionResolver(BaseResolver):
    def __init__(self, request: HttpRequest, action: str, unique_name: str) -> None:
        self.request = request
        self.action = action
        self.unique_name = unique_name

    def resolve(self) -> JsonResponse | HttpResponse:
        if self.request.content_type != 'multipart/form-data':
            return HttpResponse(
                content=f'Action requests must use multipart/form-data, got {self.request.content_type}',
                status=400,
                content_type='text/plain',
            )

        action_payload = ActionPayloadSchema.from_request(self.request)

        session = GlueSession(self.request)

        # Verify context_data hasn't been tampered with
        session.verify_action_signature(self.unique_name, action_payload.context_data)

        proxy_access = session.get_proxy_access(self.unique_name)

        proxy_instance = SUBJECT_TYPE_TO_PROXY_TYPE[
            action_payload.context_data['subject_type']
        ].from_action_request_data(
            access=proxy_access, unique_name=self.unique_name, **action_payload.context_data
        )

        action_result = proxy_instance.process_action(
            self.action, action_payload, request=self.request
        )

        # Get proxy-intrinsic response data (e.g., form errors)
        response_proxy_data = proxy_instance.get_response_proxy_data(
            action=self.action,
            action_payload=action_payload
        )

        # If the action already returned a GlueJsonResponse, inject proxy_data
        if isinstance(action_result, GlueJsonResponse):
            import json
            content = json.loads(action_result.content)
            content['proxy_data'] = response_proxy_data
            action_result.content = json.dumps(content, cls=ActionDataJSONEncoder)
            return action_result

        return JsonResponse(
            data={
                'data': action_result,
                'proxy_data': response_proxy_data,
            },
            safe=True,
            encoder=ActionDataJSONEncoder
        )
