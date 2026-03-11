from django.core import serializers
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import QuerySet, Model
from django.forms import model_to_dict


class ModelSerializingDjangoJSONEncoder(DjangoJSONEncoder):
    def default(self, obj):
        if isinstance(obj, QuerySet):
            return serializers.serialize("json", obj)

        if isinstance(obj, Model):
            return model_to_dict(obj)

        # For other types not handled by the default encoder,
        # delegate to the base class (which handles datetime, date, etc.)
        return super().default(obj)


class GlueActionJSONEncoder(DjangoJSONEncoder):
    def default(self, obj):
        if isinstance(obj, Model):
            return obj.pk

        # For other types not handled by the default encoder,
        # delegate to the base class (which handles datetime, date, etc.)
        return super().default(obj)