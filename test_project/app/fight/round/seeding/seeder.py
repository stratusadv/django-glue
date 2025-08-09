from django_spire.contrib.seeding import DjangoModelSeeder
from test_project.app.fight.round.models import FightRound


class FightRoundSeeder(DjangoModelSeeder):
    model_class = FightRound
    cache_name = 'fight_round_seeder'
    default_to = 'faker'

    fields = {
        'id': 'exclude',
        'fight': 'exclude',
        'number': ('faker', 'random_int', {'min': 1, 'max': 5}),
        'red_corner_damage_dealt': ('faker', 'random_int', {'min': 0, 'max': 100}),
        'blue_corner_damage_dealt': ('faker', 'random_int', {'min': 0, 'max': 100}),
        'red_corner_rank_points_earned': ('faker', 'random_int', {'min': 0, 'max': 10}),
        'blue_corner_rank_points_earned': ('faker', 'random_int', {'min': 0, 'max': 10}),
    }
