from django.db import models


class CapabilityLevelChoices(models.IntegerChoices):
    NOVICE = 1
    BEGINNER = 2
    INTERMEDIATE = 3
    ADVANCED = 4
    EXPERT = 5
    MASTER = 6