from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from uuid import uuid4

from django.utils.timezone import now

JOINT_METHOD_CHOICES = (
    ('rea', 'Read'),
    ('rea', 'Write'),
    ('del', 'Delete'),
)


class Joint(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, editable=False)
    object_id = models.PositiveIntegerField(editable=False)
    content_object = GenericForeignKey('content_type', 'object_id')

    key = models.CharField(max_length=36, default=uuid4, editable=False)

    method = models.CharField(max_length=3, default='rea', choices=JOINT_METHOD_CHOICES, editable=False)

    created_datetime = models.DateTimeField(default=now, editable=False)
    expiry_datetime = models.DateTimeField(default=now, editable=False)

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['key', 'content_type', 'object_id'])
        ]


class FieldJoint(Joint):
    field_name = models.CharField(max_length=64, editable=False)

    def __str__(self):
        return f'{self.content_object} {self.field_name} {self.method}'


class ModelObjectJoint(Joint):

    def __str__(self):
        return f'{self.content_object} {self.method}'


