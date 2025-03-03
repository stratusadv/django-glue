from django_glue.access.decorators import check_access
from django_glue.glue.template.actions import TemplateGlueAction
from django_glue.glue.template.post_data import GetGlueTemplatePostData

from django_glue.glue.template.session_data import TemplateSessionData
from django_glue.glue.template.glue import TemplateGlue
from django_glue.handler.handlers import BaseRequestHandler
from django_glue.response.data import JsonResponseData
from django_glue.response.responses import generate_json_200_response_data


class GetTemplateGlueHandler(BaseRequestHandler):
    action = TemplateGlueAction.GET
    _session_data_class = TemplateSessionData
    _post_data_class = GetGlueTemplatePostData

    @check_access
    def process_response_data(self) -> JsonResponseData:
        glue_template = TemplateGlue(
            unique_name=self.session_data.unique_name,
            template_name=self.session_data.template_name
        )
        rendered_template = glue_template.render_to_string(self.post_data.context_data)
        return generate_json_200_response_data(
            'THE METHOD ACTION',
            'this is a response from an model object method action!',
            data=glue_template.to_response_data(rendered_template).to_dict()
        )
