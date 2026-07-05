from typing import Any

from pydantic import BaseModel
from django.utils.datastructures import MultiValueDict
from django.core.files.uploadedfile import UploadedFile


class GlueFormProxyState(BaseModel):
    instance_data: dict[str, Any]
    errors: dict[str, Any]
    files: MultiValueDict[str, UploadedFile]
