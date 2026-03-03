from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

from test_project.gorilla.choices import FightStyleChoices


class Gorilla(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(default='', blank=True)
    age = models.IntegerField(
        default=18,
        validators=[MinValueValidator(1), MaxValueValidator(60)]
    )
    weight = models.FloatField(
        default=200.0,
        validators=[MinValueValidator(50), MaxValueValidator(500)],
        help_text='Weight in kg'
    )
    height = models.FloatField(
        default=1.8,
        validators=[MinValueValidator(1.0), MaxValueValidator(2.5)],
        help_text='Height in meters'
    )
    fight_style = models.CharField(
        max_length=20,
        choices=FightStyleChoices.choices,
        default=FightStyleChoices.BRAWLER
    )
    rank_points = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(10000)]
    )

    def __str__(self):
        return self.name
