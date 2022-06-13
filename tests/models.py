from django.db import models


class TestModel(models.Model):
    char = models.CharField(max_length=32)
    text = models.TextField()
    integer = models.IntegerField()
    decimal = models.DecimalField(max_digits=10, decimal_places=3)

    def __str__(self):
        return self.char

    def django_glue_create(self, request):
        pass

    def django_glue_view(self, request):
        pass

    def django_glue_update(self, request):
        pass

    def django_glue_delete(self, request):
        pass