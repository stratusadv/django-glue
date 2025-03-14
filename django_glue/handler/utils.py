from django_glue.handler.body import RequestBody
from django_glue.handler.enums import Connection
from django_glue.response.data import JsonResponseData

from django_glue.handler.maps import CONNECTION_TO_HANDLER_MAP
from django_glue.session import Session


def process_request(session: Session, request_body: RequestBody) -> JsonResponseData:
    # Todo: Validation errors.
    connection = Connection(session[request_body.unique_name]['connection'])

    handler_class = CONNECTION_TO_HANDLER_MAP[Connection(connection)][request_body.action]
    return handler_class(
        session=session,
        request_body=request_body
    ).process_response_data()
