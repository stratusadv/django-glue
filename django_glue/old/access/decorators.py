from django_glue.response.responses import generate_json_404_response_data


def check_access(func):
    def wrapper(self, *args, **kwargs):
        if not self.has_access():
            return generate_json_404_response_data(
                message_title='Permission Denied',
                message_body='You do not have access to this action.'
            )
        return func(self, *args, **kwargs)
    return wrapper