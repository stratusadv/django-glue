from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.http import HttpRequest

from django_glue.response import GlueResponse
from django_glue.shortcuts.glue import Glue
from test_project.gorilla.services import GorillaServiceDescriptor


class Skill(models.Model):
    """Fighting skills that gorillas can learn."""

    name = models.CharField(max_length=100)

    description = models.TextField(blank=True)
    difficulty = models.IntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(10)]
    )
    level = models.IntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(100)]
    )

    class Meta:
        db_table = 'gorilla_skill'

    def __str__(self) -> str:
        return self.name


class Gorilla(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(default='', blank=True)
    age = models.IntegerField(default=18, validators=[MinValueValidator(1), MaxValueValidator(60)])
    weight = models.FloatField(
        default=200.0,
        validators=[MinValueValidator(50), MaxValueValidator(500)],
        help_text='Weight in kg',
    )
    height = models.FloatField(
        default=1.8,
        validators=[MinValueValidator(1.0), MaxValueValidator(2.5)],
        help_text='Height in meters',
    )
    rank_points = models.IntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(10000)]
    )

    profile_photo = models.ImageField(
        upload_to='gorilla_photos/', blank=True, null=True, help_text='Fighter profile photo'
    )

    skills = models.ManyToManyField('Skill', related_name='gorillas', blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    services = Glue.attribute(GorillaServiceDescriptor(), access=Glue.Access.CHANGE)

    class Meta:
        db_table = 'gorilla'

    def __str__(self) -> str:
        return self.name

    @Glue.attribute(access=Glue.Access.DELETE)
    def battle_cry(self, request: HttpRequest, intensity: str = 'normal') -> GlueResponse:
        """
        Demonstrates a custom Glue action routed from frontend to server.

        The frontend calls: gorilla.battle_cry({intensity: 'fierce'})
        This routes through django-glue to invoke this method on the server,
        with the request object and named parameters automatically passed.
        """
        cries = {
            'whisper': f'{self.name} softly grunts... 🦍',
            'normal': f'{self.name} beats their chest! 🦍💪',
            'fierce': f'{self.name} ROARS WITH PRIMAL FURY! 🦍🔥👊',
        }
        cry = cries.get(intensity, cries['normal'])

        print(
            f"[Battle Cry] User '{request.user}' triggered "
            f"{self.name}'s battle cry (intensity: {intensity})"
        )

        return GlueResponse(
            result={
                'success': True,
                'gorilla': self.name,
                'cry': cry,
                'intensity': intensity,
                'triggered_by': str(request.user),
            },
            messages=[
                GlueResponse.Message(
                    GlueResponse.Message.Level.SUCCESS,
                    f'{cry} (triggered by {request.user})',
                )
            ],
        )

    @Glue.attribute(access=Glue.Access.VIEW)
    def shout(self, volume: int) -> str:
        return 'A' * volume

    @Glue.attribute(access=Glue.Access.VIEW)
    def something(self) -> None:
        self.age = self.age + 1
        self.save()

