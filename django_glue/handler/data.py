import json
from dataclasses import dataclass

from django_glue.access.enums import GlueAction


# Todo: Should there be a structure of data that we expect to receive from the JS front end?
class GlueBodyData:
    def __init__(self, request_body):
        self.data = json.loads(request_body.decode('utf-8'))
        self.unique_name = self.data['unique_name']
        self.action = self.data['action']

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value
