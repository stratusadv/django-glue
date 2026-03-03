from django.db import models


class LocationChoices(models.TextChoices):
    THUNDERDOME = 'thu', 'Thunderdome'
    COLOSSEUM = 'col', 'Colosseum'
    ABANDONED_MALL = 'aml', 'Abandoned Mall'
    NINJA_DOJO = 'nin', 'Ninja Dojo'
    DINOSAUR_ISLAND = 'din', 'Dinosaur Island'
    VOLCANO_CRATER = 'vol', 'Volcano Crater'
    PIRATE_COVE = 'pir', 'Pirate Cove'
    ALIEN_WASTELAND = 'ali', 'Alien Wasteland'


class WeatherConditionChoices(models.TextChoices):
    PERFECT_BLUE_SKY = 'pbs', 'Perfect Blue Sky'
    OMINOUS_CLOUDS = 'omc', 'Ominous Clouds'
    TORRENTIAL_DOWNPOUR = 'tor', 'Torrential Downpour'
    APOCALYPTIC_THUNDER = 'apt', 'Apocalyptic Thunder'
    BLIZZARD_FURY = 'blz', 'Blizzard Fury'
    SCORCHING_INFERNO = 'scr', 'Scorching Inferno'
    ARCTIC_FREEZE = 'arc', 'Arctic Freeze'
    HURRICANE_FORCE = 'hur', 'Hurricane Force'
    MYSTERIOUS_MIST = 'mst', 'Mysterious Mist'


class TerrainTypeChoices(models.TextChoices):
    STEEL_DEATH_CAGE = 'sdc', 'Steel Death Cage'
    FLAMING_RING_OF_DOOM = 'frd', 'Flaming Ring of Doom'
    BOUNCY_TRAMPOLINE_FLOOR = 'btf', 'Bouncy Trampoline Floor'
    ELECTRIC_GRASS_FIELD = 'egf', 'Electric Grass Field'
    QUICKSAND_TRAP = 'qst', 'Quicksand Trap'
    CHOCOLATE_PUDDING_PIT = 'cpp', 'Chocolate Pudding Pit'
    LAVA_FLOOR = 'lva', 'Lava Floor'
    SPIKY_BOULDER_FIELD = 'sbf', 'Spiky Boulder Field'
    SHARK_INFESTED_WATERS = 'siw', 'Shark Infested Waters'


class FightStatusChoices(models.TextChoices):
    SCHEDULED = 'sch', 'Scheduled'
    IN_PROGRESS = 'inp', 'In Progress'
    COMPLETED = 'cmp', 'Completed'
    CANCELLED = 'cnc', 'Cancelled'
    POSTPONED = 'pst', 'Postponed'
    DRAW = 'drw', 'Draw'
    NO_CONTEST = 'nct', 'No Contest'
