from django.db import models
from django.utils.timezone import now


class TestModel(models.Model):
    first_name = models.CharField(max_length=32)
    last_name = models.CharField(max_length=32)
    description = models.TextField()
    favorite_number = models.IntegerField()
    anniversary_datetime = models.DateTimeField(default=now)
    birth_date = models.DateField(default=now)
    weight_lbs = models.DecimalField(max_digits=7, decimal_places=3)

    def __str__(self):
        return f'{self.first_name} {self.last_name}'

    def django_glue_create(self, request):
        pass

    def django_glue_update(self, request):
        pass

    def django_glue_delete(self, request):
        pass

    def django_glue_view(self, request):
        pass

