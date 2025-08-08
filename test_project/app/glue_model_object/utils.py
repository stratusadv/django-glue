import random

from test_project.app.glue_model_object import models

FIRST_NAME_TUPLE = (
    'Fred',
    'Jane',
    'Janet',
    'Austin',
    'Johnny',
    'Nathan',
    'Robert',
    'Ted',
    'Wesley',
)

LAST_NAME_TUPLE = (
    'Doe',
    'Johnson',
    'Hansen',
    'Mancal',
    'Smith',
    'Waldern',
    'Howery',
    'Wilson',
    'Sauer',
)

DESCRIPTION_WORD_TUPLE = (
    'a',
    'are',
    'artsy',
    'awesome',
    'balloon',
    'boring',
    'can',
    'cat',
    'cool',
    'dripping',
    'dog',
    'eggs',
    'extra',
    'fast',
    'finished',
    'fly',
    'goal',
    'graduated',
    'handy',
    'has',
    'has',
    'have',
    'how',
    'I',
    'it',
    'junk',
    'killer',
    'loves cars',
    'mother',
    'missle',
    'need',
    'opposite',
    'panther',
    'quiz',
    'rugged',
    'she',
    'started',
    'stupid',
    'taco',
    'that',
    'then',
    'there',
    'to',
    'ugly',
    'vixen',
    'want',
    'when',
    'where',
    'when',
    'wood carving',
    'xavier',
    'you',
    'zebra',
)

def generate_randomized_test_model(limit=5):
    new_description = ''

    for x in range(20):
        new_description += f'{DESCRIPTION_WORD_TUPLE[random.randint(0, (len(DESCRIPTION_WORD_TUPLE) - 1))]} '

    test_model_object = models.TestGlueModelObject.objects.create(
        first_name=FIRST_NAME_TUPLE[random.randint(0, (len(FIRST_NAME_TUPLE) - 1))],
        last_name=LAST_NAME_TUPLE[random.randint(0, (len(LAST_NAME_TUPLE) - 1))],
        description=new_description,
        favorite_number=random.randint(0, 999),
        weight_lbs=round(random.uniform(80.001, 400.123), 3),
        best_friend=models.TestGlueModelObject.objects.first()
    )

    exclude_test_model = models.TestGlueModelObject.objects.all().order_by('-id')[:limit]
    models.TestGlueModelObject.objects.exclude(pk__in=[x.id for x in exclude_test_model]).delete()

    return test_model_object