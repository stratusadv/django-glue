from django.db import models

class Monitor(models.Model):
    key = models.CharField(max_length=32)

    def has_changed(self, key):
        if key == self.key:
            return False
        else:
            return True

    def set_key(self, key):
        pass

    def get_key(self):
        pass