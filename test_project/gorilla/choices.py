from django.db import models


class FightStyleChoices(models.TextChoices):
    BOXING = 'box', 'Boxing'
    MUAY_THAI = 'mua', 'Muay Thai'
    BRAZILIAN_JIU_JITSU = 'bjj', 'Brazilian Jiu-Jitsu'
    WRESTLING = 'wre', 'Wrestling'
    KARATE = 'kar', 'Karate'
    TAEKWONDO = 'tae', 'Taekwondo'
    JUDO = 'jud', 'Judo'
    KICKBOXING = 'kic', 'Kickboxing'
    MIXED = 'mix', 'Mixed Style'
    BRAWLER = 'bra', 'Brawler'
