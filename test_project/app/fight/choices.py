from django.db import models


class LocationChoices(models.TextChoices):
    THUNDERDOME = 'thu'
    COLOSSEUM = 'col'
    ABANDONED_MALL = 'aml'
    NINJA_DOJO = 'nin'
    DINOSAUR_ISLAND = 'din'
    VOLCANO_CRATER = 'vol'
    PIRATE_COVE = 'pir'
    ALIEN_WASTELAND = 'ali'


class WeatherConditionChoices(models.TextChoices):
    PERFECT_BLUE_SKY = 'pbs'
    OMINOUS_CLOUDS = 'omc'
    TORRENTIAL_DOWNPOUR = 'tor'
    APOCALYPTIC_THUNDER = 'apt'
    BLIZZARD_FURY = 'blz'
    SCORCHING_INFERNO = 'scr'
    ARCTIC_FREEZE = 'arc'
    HURRICANE_FORCE = 'hur'
    MYSTERIOUS_MIST = 'mst'


class TerrainTypeChoices(models.TextChoices):
    STEEL_DEATH_CAGE = 'sdc'
    FLAMING_RING_OF_DOOM = 'frd'
    BOUNCY_TRAMPOLINE_FLOOR = 'btf'
    ELECTRIC_GRASS_FIELD = 'egf'
    QUICKSAND_TRAP = 'qst'
    CHOCOLATE_PUDDING_PIT = 'cpp'
    LAVA_FLOOR = 'lva'
    SPIKY_BOULDER_FIELD = 'sbf'
    SHARK_INFESTED_WATERS = 'siw'


class FightStatusChoices(models.TextChoices):
    SCHEDULED = 'sch'
    IN_PROGRESS = 'inp'
    COMPLETED = 'cmp'
    CANCELLED = 'cnc'
    POSTPONED = 'pst'
    DRAW = 'drw'
    NO_CONTEST = 'nct'