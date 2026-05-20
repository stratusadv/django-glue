from django_glue.exceptions import GlueError


class GlueResolverError(GlueError):
    def __init__(self, response_error: str, response_status: int) -> None:
        self.response_error = response_error
        self.response_status = response_status
        super().__init__(response_error)
