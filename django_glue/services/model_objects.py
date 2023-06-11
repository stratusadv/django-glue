from django.contrib.contenttypes.models import ContentType

from django_glue.data_classes import GlueJsonResponseData, GlueJsonData, GlueBodyData, GlueMetaData
from django_glue.responses import generate_json_200_response_data
from django_glue.services.services import Service
from django_glue.utils import generate_simple_field_dict


class GlueModelObjectService(Service):
    def __init__(self, meta_data: GlueMetaData) -> None:
        self.meta_data = meta_data
        self.model_class = None
        self.object = None

    def load_object(self):
        self.model_class = ContentType.objects.get_by_natural_key(
            self.meta_data.app_label,
            self.meta_data.model
        ).model_class()

        self.object = self.model_class.objects.get(pk=self.meta_data.object_pk)

    def process_get_action(self, body_data: GlueBodyData) -> GlueJsonResponseData:
        self.load_object()
        json_data = GlueJsonData()

        json_data.simple_fields = generate_simple_field_dict(
            self.object,
            self.meta_data.fields,
            self.meta_data.exclude,
        )

        json_data.simple_fields['first_name'] = 'Humbugery'

        return generate_json_200_response_data(
            'THE GET ACTION',
            'this is a response from an empty model object get action!!! stay tuned!',
            json_data,
        )

    def process_create_action(self, body_data: GlueBodyData) -> GlueJsonResponseData:
        pass

    def process_update_action(self, body_data: GlueBodyData) -> GlueJsonResponseData:
        pass

    def process_delete_action(self, body_data: GlueBodyData) -> GlueJsonResponseData:
        pass

    def process_method_action(self, body_data: GlueBodyData) -> GlueJsonResponseData:
        pass
