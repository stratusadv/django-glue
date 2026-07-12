from django.core.files.uploadedfile import UploadedFile
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import QuerySet, Model
from django.db.models.fields.files import FieldFile
from django.forms import model_to_dict


class BoundAttributeDataJSONEncoder(DjangoJSONEncoder):
    def default(self, obj):
        if isinstance(obj, Model):
            return model_to_dict(obj)

        if isinstance(obj, QuerySet):
            return [model_to_dict(obj) for obj in obj]

        if isinstance(obj, FieldFile):
            try:
                return {'name': obj.name, 'size': obj.size, 'url': obj.url, 'path': obj.path}
            except ValueError:
                return None

        if isinstance(obj, UploadedFile):
            try:
                return {'name': obj.name, 'size': obj.size}
            except ValueError:
                return None

        # For other types not handled by the default encoder,
        # delegate to the base class (which handles datetime, date, etc.)
        return super().default(obj)
