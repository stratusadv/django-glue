from django.db import models
from django.utils.timezone import now

from django_glue.decorators import glue_method


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

    @glue_method
    def decorated_method(self, request):
        pass

    def undecorated_method(self, request):
        pass


class BigTestModel(models.Model):
    big_integer_field = models.BigIntegerField()
    binary_field = models.BinaryField()
    boolean_field = models.BooleanField()
    char_field = models.CharField(max_length=8)
    date_field = models.DateField()
    date_time_field = models.DateTimeField()
    decimal_field = models.DecimalField(decimal_places=2, max_digits=6)
    duration_field = models.DurationField()
    email_field = models.EmailField()
    file_path_field = models.FilePathField(path='/static')
    float_field = models.FloatField()
    generic_ip_address_field = models.GenericIPAddressField()
    ip_address_field = models.GenericIPAddressField()
    integer_field = models.IntegerField()
    positive_big_integer_field = models.PositiveBigIntegerField()
    positive_integer_field = models.PositiveIntegerField()
    positive_small_integer_field = models.PositiveSmallIntegerField()
    slug_field = models.SlugField()
    small_integer_field = models.SmallIntegerField()
    text_field = models.TextField()
    time_field = models.TimeField()
    url_field = models.URLField()
    uuid_field = models.UUIDField()

    def __str__(self):
        return f'{self.char_field}'



