from contextlib import suppress
from typing import Any

from django.core.files.base import File
from django.core.files.uploadedfile import UploadedFile
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Model, QuerySet
from django.db.models.fields.files import FieldFile
from django.forms import model_to_dict
from pydantic import BaseModel


def _serialize_field_file(file: FieldFile) -> dict | None:
    """Serialize a FieldFile (model file field) to a dict."""
    if not file:
        return None

    result = {'name': file.name}

    with suppress(ValueError):
        result['url'] = file.url

    with suppress(ValueError, NotImplementedError):
        result['path'] = file.path

    return result


def _serialize_uploaded_file(file: UploadedFile) -> dict:
    """Serialize an UploadedFile (form submission) to a dict."""
    return {'name': file.name}


class GlueResponseJSONEncoder(DjangoJSONEncoder):
    def default(self, o: Any) -> Any:  # noqa: PLR0911
        if isinstance(o, BaseModel):
            return o.model_dump()

        if isinstance(o, Model):
            return model_to_dict(o)

        if isinstance(o, QuerySet):
            return [model_to_dict(item) for item in o]

        if isinstance(o, FieldFile):
            return _serialize_field_file(o)

        if isinstance(o, UploadedFile):
            return _serialize_uploaded_file(o)

        if isinstance(o, File):
            return {'name': o.name}

        # Handle memoryview objects (returned by PostgreSQL for BinaryField)
        if isinstance(o, memoryview):
            return o.tobytes().decode('utf-8', errors='replace')

        # Handle bytes objects
        if isinstance(o, bytes):
            return o.decode('utf-8', errors='replace')

        # For other types not handled by the default encoder,
        # delegate to the base class (which handles datetime, date, etc.)
        return super().default(o)
