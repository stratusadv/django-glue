from django_spire.contrib.seeding import DjangoModelSeeder
from test_project.app.fight.models import Fight


class FightSeeder(DjangoModelSeeder):
    model_class = Fight
    cache_name = 'fight_seeder'
    default_to = 'faker'

    fields = {
        'id': 'exclude',
        'name': ('llm', 'Generate a name for an MMA fight between two gorillas.'),
        'description': ('llm', 'Write a brief description of an intense MMA fight between two gorillas.'),
        'red_corner': 'exclude',
        'blue_corner': 'exclude',
        'winner': 'exclude',
        'loser': 'exclude',
        'spectator_count': ('faker', 'random_int', {'min': 0, 'max': 10000}),
    }
