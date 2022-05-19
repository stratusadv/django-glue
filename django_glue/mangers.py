from django.db import models


class MonitorManager(models.Manager):
    def set_key(self, key):
        pass