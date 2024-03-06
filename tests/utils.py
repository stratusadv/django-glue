import random, datetime
import uuid

from django.utils.timezone import now

from tests.models import TestModel, BigTestModel

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


def custom_test_function(request):
    return 'Hello World'


def generate_randomized_test_model(limit=5):
    new_description = ''
    for x in range(20):
        new_description += f'{DESCRIPTION_WORD_TUPLE[random.randint(0, (len(DESCRIPTION_WORD_TUPLE) - 1))]} '

    test_model_object = TestModel.objects.create(
        first_name=FIRST_NAME_TUPLE[random.randint(0, (len(FIRST_NAME_TUPLE) - 1))],
        last_name=LAST_NAME_TUPLE[random.randint(0, (len(LAST_NAME_TUPLE) - 1))],
        description=new_description,
        favorite_number=random.randint(0, 999),
        weight_lbs=round(random.uniform(80.001, 400.123), 3),
    )

    exclude_test_model = TestModel.objects.all().order_by('-id')[:limit]
    TestModel.objects.exclude(pk__in=exclude_test_model).delete()

    return test_model_object


def generate_big_test_model(limit=5):
    big_test_model = BigTestModel.objects.create(
        big_integer_field=-8294853213,
        binary_field=bytes('Some Bytes', 'utf-8'),
        boolean_field=False,
        char_field='Word',
        date_field=now(),
        date_time_field=now(),
        decimal_field=19.88,
        duration_field=datetime.timedelta(days=1, minutes=60),
        email_field='me@here.com',
        file_path_field='static.css',
        foreign_key=TestModel.objects.first(),
        float_field=88.19,
        generic_ip_address_field='127.0.01',
        ip_address_field='0.0.0.0',
        integer_field=-23,
        positive_big_integer_field=3247238947238,
        positive_integer_field=1312321,
        positive_small_integer_field=9,
        slug_field='',
        small_integer_field=-7,
        text_field='This is a bunch of text in the text field that is written to take up a lot of space',
        time_field=datetime.time(10, 20, 30),
        url_field='https://www.stratusadv.com',
        uuid_field=uuid.uuid4()
    )

    exclude_test_model = BigTestModel.objects.all().order_by('-id')[:limit]
    BigTestModel.objects.exclude(pk__in=exclude_test_model).delete()

    return big_test_model


def test_glue_function(greeting: str, name: str):
    return f'{greeting}, {name}!'
