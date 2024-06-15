import uuid

from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils.timezone import now, localdate


class TestModel(models.Model):
    first_name = models.CharField(max_length=32)
    last_name = models.CharField(max_length=32)
    description = models.TextField()
    personality_type = models.CharField(
        max_length=3,
        choices=[('int', 'Introvert'), ('ext', 'Extrovert')],
        default='int'
    )
    email = models.EmailField(blank=True, null=True)
    favorite_number = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(999)])
    anniversary_datetime = models.DateTimeField(default=now)
    birth_date = models.DateField(default=localdate)
    weight_lbs = models.DecimalField(max_digits=7, decimal_places=3)

    bed_time = models.TimeField(default='20:00')
    likes_to_party = models.BooleanField(default=True)

    def __str__(self):
        return f'{self.first_name} {self.last_name}'

    def is_lighter_than(self, check_weight: float) -> bool:
        if self.weight_lbs < check_weight:
            return True
        return False

    def get_full_name(self):
        return f'{self.first_name} {self.last_name}'


class UuidTestModel(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    title = models.CharField(max_length=32)

    def __str__(self):
        return self.title


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
    foreign_key = models.ForeignKey(TestModel, on_delete=models.CASCADE)
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
