import json

from django_glue.access.enums import GlueAction


class GlueBodyData:
    def __init__(self, request_body):
        # Todo: We always need to pass a unique name
        self.data = json.loads(request_body.decode('utf-8'))
        self.glue_action = GlueAction(self.data['action'])

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value

    @property
    def action(self) -> GlueAction:
        return self.glue_action

    @property
    def unique_name(self) -> str:
        return self.data['unique_name']
