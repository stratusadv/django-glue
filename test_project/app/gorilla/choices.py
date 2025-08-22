from django.db import models


class FightStyleChoices(models.TextChoices):
    BOXING = 'box'
    MUAY_THAI = 'mua'
    BRAZILIAN_JIU_JITSU = 'bjj'
    WRESTLING = 'wre'
    KARATE = 'kar'
    TAEKWONDO = 'tae'
    JUDO = 'jud'
    KICKBOXING = 'kic'
    MIXED = 'mix', 'Mixed Style'
    BRAWLER = 'bra'