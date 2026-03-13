from django.core.files.uploadedfile import InMemoryUploadedFile, UploadedFile
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import QuerySet, Model, FileField
from django.db.models.fields.files import FieldFile


class GlueActionDataJSONEncoder(DjangoJSONEncoder):
    def default(self, obj):
        if isinstance(obj, Model):
            return obj.pk

        if isinstance(obj, QuerySet):
            return [obj.pk for obj in obj]

        if isinstance(obj, FieldFile) or isinstance(obj, UploadedFile):
            try:
                return {
                    "name": obj.name,
                    "size": obj.size,
                    "url": obj.url,
                    "path": obj.path,
                }
            except ValueError:
                return None

        # For other types not handled by the default encoder,
        # delegate to the base class (which handles datetime, date, etc.)
        return super().default(obj)
