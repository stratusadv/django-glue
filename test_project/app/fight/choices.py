from django.db import models


class LocationChoices(models.TextChoices):
    ARENA = 'are'
    STADIUM = 'sta'
    OUTDOOR = 'out'
    GYM = 'gym'
    JUNGLE = 'jun'
    MOUNTAIN = 'mtn'
    BEACH = 'bch'
    DESERT = 'des'


class WeatherConditionChoices(models.TextChoices):
    CLEAR = 'clr'
    CLOUDY = 'cld'
    RAINY = 'ran'
    STORMY = 'stm'
    SNOWY = 'snw'
    HOT = 'hot'
    COLD = 'col'
    WINDY = 'wnd'
    FOGGY = 'fog'


class TerrainTypeChoices(models.TextChoices):
    CAGE = 'cag'
    RING = 'rng'
    MAT = 'mat'
    GRASS = 'grs'
    SAND = 'snd'
    MUD = 'mud'
    CONCRETE = 'con'
    ROCKY = 'rck'
    WATER = 'wtr'


class FightStatusChoices(models.TextChoices):
    SCHEDULED = 'sch'
    IN_PROGRESS = 'inp'
    COMPLETED = 'cmp'
    CANCELLED = 'cnc'
    POSTPONED = 'pst'
    DRAW = 'drw'
    NO_CONTEST = 'nct'