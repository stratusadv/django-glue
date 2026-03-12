from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class Skill(models.Model):
    """Fighting skills that gorillas can learn."""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    difficulty = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(10)]
    )
    level = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(100)]
    )

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'gorilla_skill'


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
    rank_points = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(10000)]
    )

    profile_photo = models.ImageField(
        upload_to='gorilla_photos/',
        blank=True,
        null=True,
        help_text='Fighter profile photo'
    )

    skills = models.ManyToManyField(
        'Skill',
        related_name='gorillas',
        blank=True,
    )

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'gorilla'
