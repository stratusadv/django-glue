from django.db import models


class CapabilityTypeChoices(models.TextChoices):
    PHYSICAL_ATTRIBUTE = 'phy'
    STRIKING_SKILL = 'ski'
    GRAPPLING_SKILL = 'gra'
    DEFENSIVE_SKILL = 'def'
    SPECIAL_TECHNIQUE = 'spe'
    FIGHT_STYLE = 'fig'


class CapabilityLevelChoices(models.IntegerChoices):
    NOVICE = 1
    BEGINNER = 2
    INTERMEDIATE = 3
    ADVANCED = 4
    EXPERT = 5
    MASTER = 6