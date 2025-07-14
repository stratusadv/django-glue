from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils.timezone import now, localdate

from test_project.app.glue_model_object import querysets


class TestGlueModelObject(models.Model):
    first_name = models.CharField(max_length=32)
    last_name = models.CharField(max_length=32)
    description = models.TextField()
    personality_type = models.CharField(
        max_length=3,
        choices=[('int', 'Introvert'), ('ext', 'Extrovert')],
        default='int',
    )
    email = models.EmailField(blank=True, null=True)
    favorite_number = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(999)])
    anniversary_datetime = models.DateTimeField(default=now)
    birth_date = models.DateField(default=localdate)
    weight_lbs = models.DecimalField(max_digits=7, decimal_places=3)

    best_friend = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        blank=True,
        null=True
    )

    bed_time = models.TimeField(default='20:00')
    likes_to_party = models.BooleanField(default=True)

    objects = querysets.TestGlueModelObjectQuerySet.as_manager()

    def __str__(self):
        return f'{self.first_name} {self.last_name}'

    def is_lighter_than(self, check_weight: float) -> bool:
        if self.weight_lbs < check_weight:
            return True
        return False

    def get_full_name(self):
        return f'{self.first_name} {self.last_name}'
