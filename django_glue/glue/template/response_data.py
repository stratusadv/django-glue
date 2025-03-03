from dataclasses import dataclass

from django_glue.response.data import BaseJsonData


@dataclass
class GlueTemplateJsonData(BaseJsonData):
    rendered_template: str

    def to_dict(self):
        return {'rendered_template': self.rendered_template}


