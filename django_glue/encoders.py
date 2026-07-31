import json

from django.core.files.base import File
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Model, QuerySet
from django.forms import model_to_dict
from pydantic import BaseModel


def _serialize_file(file: File) -> dict | None:
    """Serialize a Django File object to a dict.

    Includes name, url, and path when available. Size is intentionally omitted
    because it requires a HEAD request to remote storage backends like S3,
    which adds ~70ms latency per file.
    """
    result = {'name': file.name}

    # url - only FieldFile has this, and only if file exists
    try:
        result['url'] = file.url
    except (AttributeError, ValueError):
        # AttributeError: UploadedFile doesn't have url
        # ValueError: No file associated with this field
        pass

    # path - only local storage backends support this
    try:
        result['path'] = file.path
    except (AttributeError, NotImplementedError):
        # AttributeError: UploadedFile doesn't have path
        # NotImplementedError: Remote storage (S3, etc.) doesn't support absolute paths
        pass

    return result or None


class GlueResponseJSONEncoder(DjangoJSONEncoder):
    def default(self, obj):
        if isinstance(obj, BaseModel):
            return obj.model_dump()

        if isinstance(obj, Model):
            return model_to_dict(obj)

        if isinstance(obj, QuerySet):
            return [model_to_dict(item) for item in obj]

        if isinstance(obj, File):
            return _serialize_file(obj)

        # Handle memoryview objects (returned by PostgreSQL for BinaryField)
        if isinstance(obj, memoryview):
            return obj.tobytes().decode('utf-8', errors='replace')

        # Handle bytes objects
        if isinstance(obj, bytes):
            return obj.decode('utf-8', errors='replace')

        # For other types not handled by the default encoder,
        # delegate to the base class (which handles datetime, date, etc.)
        return super().default(obj)
