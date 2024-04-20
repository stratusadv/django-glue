from dataclasses import field, dataclass

from django_glue.entities.model_object.responses import GlueModelObjectJsonData
from django_glue.response.data import GlueJsonData


@dataclass
class GlueTemplateJsonData(GlueJsonData):
    rendered_template: str

    def to_dict(self):
        return {'rendered_template': self.rendered_template}

