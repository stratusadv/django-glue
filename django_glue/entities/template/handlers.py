from django_glue.access.decorators import check_access
from django_glue.entities.template.actions import GlueTemplateAction
from django_glue.entities.template.post_data import GetGlueTemplatePostData

from django_glue.entities.template.sessions import TemplateSessionData
from django_glue.entities.template.entities import GlueTemplate
from django_glue.handler.handlers import GlueRequestHandler
from django_glue.response.data import GlueJsonResponseData
from django_glue.response.responses import generate_json_200_response_data


class GetGlueTemplateHandler(GlueRequestHandler):
    action = GlueTemplateAction.GET
    _session_data_class = TemplateSessionData
    _post_data_class = GetGlueTemplatePostData

    @check_access
    def process_response(self) -> GlueJsonResponseData:
        glue_template = GlueTemplate(
            unique_name=self.session_data.unique_name,
            template_name=self.session_data.template_name
        )
        rendered_template = glue_template.render_to_string(self.post_data.context_data)
        return generate_json_200_response_data(
            'THE METHOD ACTION',
            'this is a response from an model object method action!',
            data=glue_template.to_response_data(rendered_template).to_dict()
        )
