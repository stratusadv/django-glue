from django.db import models


class TestModel(models.Model):
    char = models.CharField(max_length=32)
    text = models.TextField()
    integer = models.IntegerField()
    decimal = models.DecimalField(max_digits=10, decimal_places=3)

    def __str__(self):
        return self.char