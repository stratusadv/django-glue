from django_glue.constants import GLUE_TYPE_KEY
from django_glue.glue.enums import GlueType
from django_glue.handler.body import RequestBody
from django_glue.handler.maps import GLUE_TYPE_TO_HANDLER_MAP
from django_glue.response.data import JsonResponseData
from django_glue.session import Session


def process_request(session: Session, request_body: RequestBody) -> JsonResponseData:
    # Todo: Validation errors.
    glue_type = GlueType(session[request_body.unique_name][GLUE_TYPE_KEY])

    handler_class = GLUE_TYPE_TO_HANDLER_MAP[GlueType(glue_type)][request_body.action]

    return handler_class(
        session=session,
        request_body=request_body
    ).process_response_data()
