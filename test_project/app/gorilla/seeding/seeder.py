from django_spire.contrib.seeding import DjangoModelSeeder
from test_project.app.gorilla.models import Gorilla


class GorillaSeeder(DjangoModelSeeder):
    model_class = Gorilla
    cache_name = 'gorilla_seeder'
    cache_seed = False
    default_to = 'faker'

    fields = {
        'id': 'exclude',
        'name': ('llm', 'Generate a realistic name for an MMA fighting gorilla'),
        'description': ('llm', 'Write a detailed description for an MMA fighting gorilla'),
        'age': ('faker', 'random_int', {'min': 18, 'max': 42}),
        'weight': ('faker', 'pyfloat', {'left_digits': 3, 'right_digits': 1, 'positive': True}),
        'height': ('faker', 'pyfloat', {'left_digits': 2, 'right_digits': 2, 'positive': True}),
        'fight_style': 'faker',
        'rank_points': ('faker', 'random_int', {'min': 0, 'max': 1000})
    }