from django_glue.handler.body_data import GlueBodyData
from django_glue.handler.enums import Connection
from django_glue.response.data import JsonResponseData

from django_glue.handler.maps import CONNECTION_TO_HANDLER_MAP
from django_glue.session import GlueSession


def process_glue_request(glue_session: GlueSession, glue_body_data: GlueBodyData) -> JsonResponseData:
    # Todo: Validation errors.
    connection = Connection(glue_session[glue_body_data.unique_name]['connection'])

    handler_class = CONNECTION_TO_HANDLER_MAP[Connection(connection)][glue_body_data.action]
    return handler_class(
        glue_session=glue_session,
        glue_body_data=glue_body_data
    ).process_response_data()
