from django.contrib import admin

from django_glue import models

admin.site.register(models.FieldGlue)
admin.site.register(models.ObjectGlue)
