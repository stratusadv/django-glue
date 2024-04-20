import json
from dataclasses import dataclass
from typing import Any

from django.core.serializers.json import DjangoJSONEncoder

from django_glue.response.data import GlueJsonData


@dataclass
class GlueFunctionJsonData(GlueJsonData):
    function_return: Any

    def to_dict(self):
        return json.loads(
            json.dumps(
                obj={'function_return': self.function_return},
                cls=DjangoJSONEncoder
            )
        )


