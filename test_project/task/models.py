from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class Task(models.Model):
    title = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    done = models.BooleanField(default=False)
    order = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(1000)]
    )
