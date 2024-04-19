from django_glue.handler.data import GlueBodyData
from django_glue.handler.enums import GlueConnection
from django_glue.response.data import GlueJsonResponseData

from django_glue.handler.maps import CONNECTION_TO_HANDLER_MAP
from django_glue.session import GlueSession


def process_glue_request(glue_session: GlueSession, glue_body_data: GlueBodyData) -> GlueJsonResponseData:
    # Todo: Validation errors.
    connection = GlueConnection(glue_session[glue_body_data.unique_name]['connection'])
    handler_class = CONNECTION_TO_HANDLER_MAP[GlueConnection(connection)][glue_body_data.action]
    return handler_class(
        unique_name=glue_body_data.unique_name,
        glue_session=glue_session,
        glue_body_data=glue_body_data
    ).process_response()
