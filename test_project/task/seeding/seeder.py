from __future__ import annotations

from django_spire.contrib.seeding import DjangoModelSeeder

from test_project.task.models import Task


class TaskSeeder(DjangoModelSeeder):
    model_class = Task
    cache_seed = False

    fields = {
        'id': 'exclude',
        'title': ('faker', 'sentence', {'nb_words': 4}),
        'description': ('faker', 'paragraph', {'nb_sentences': 2}),
        'done': ('faker', 'boolean'),
        'order': ('faker', 'random_int', {'min': 1, 'max': 100}),
    }
    default_to = 'faker'