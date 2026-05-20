from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods

from django_glue.schemas.action_payload_schema import ActionPayloadSchema
from django_glue.encoders import GlueActionDataJSONEncoder
from django_glue.maps import SUBJECT_TYPE_TO_PROXY_TYPE
from django_glue.session import GlueSession


@require_http_methods(['POST'])
def action_view(request: HttpRequest, unique_name: str, action: str) -> JsonResponse | HttpResponse:
    if request.content_type not in ['application/json', 'multipart/form-data']:
        return HttpResponse(
            content=f'Unsupported media type {request.content_type}',
            status=400,
            content_type='text/plain',
        )

    action_payload = ActionPayloadSchema.from_request(request)

    proxy_access = GlueSession(request).get_proxy_access(unique_name)

    proxy_instance = SUBJECT_TYPE_TO_PROXY_TYPE[
        action_payload.context_data['subject_type']
    ].from_action_request_data(
        access=proxy_access, unique_name=unique_name, **action_payload.context_data
    )

    action_response_data = proxy_instance.process_action(action, action_payload)

    return JsonResponse(data=action_response_data, safe=False, encoder=GlueActionDataJSONEncoder)
