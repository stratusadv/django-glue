from django.db import  models


class TestGlueModelObjectQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True, is_deleted=False)
