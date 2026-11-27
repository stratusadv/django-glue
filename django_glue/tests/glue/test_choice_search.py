from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.db.models import F
from django.test import RequestFactory

from django_glue import Glue
from django_glue.glue.options.django.choices import GlueRelatedModelChoices
from test_project.fight.models import Fight
from test_project.gorilla.models import Gorilla

if TYPE_CHECKING:
    from django.db.models import QuerySet

pytestmark = pytest.mark.django_db


def _load_labels(queryset: QuerySet, search: str = '') -> list[str]:
    request = RequestFactory().get('/page/')
    result = GlueRelatedModelChoices(queryset).load(search=search, request=request)
    return [item['label'] for item in result['results']]


def test_multi_word_search_matches_across_multiple_fields_and_ranks_by_relevance() -> None:
    Gorilla.objects.create(name='Alpha Logistics', description='Portal Rewrite')
    Gorilla.objects.create(name='Acme Corp', description='Billing App')
    Gorilla.objects.create(name='Beta Corp', description='Acme Portal')
    Gorilla.objects.create(name='Acme Corp', description='Portal Rewrite')
    Gorilla.objects.create(name='Unrelated', description='Something Else')

    queryset = Glue.choices(
        Gorilla.objects.order_by('name', 'description'),
        search_fields=('name', 'description'),
        fields=('description',),
    )

    request = RequestFactory().get('/page/')
    result = GlueRelatedModelChoices(queryset).load(search='acme portal', request=request)
    pairs = [(item['label'], item['obj']['description']) for item in result['results']]

    assert pairs == [
        ('Acme Corp', 'Portal Rewrite'),
        ('Beta Corp', 'Acme Portal'),
        ('Acme Corp', 'Billing App'),
        ('Alpha Logistics', 'Portal Rewrite'),
    ]


def test_multi_word_search_is_order_independent_and_case_insensitive() -> None:
    Gorilla.objects.create(name='Acme Corp', description='Portal Rewrite')
    Gorilla.objects.create(name='Other', description='Portal')

    queryset = Glue.choices(
        Gorilla.objects.order_by('name'),
        search_fields=('name', 'description'),
    )

    assert _load_labels(queryset, search='PORTAL acme') == ['Acme Corp', 'Other']


def test_multi_word_search_on_single_field_ranks_more_word_hits_first() -> None:
    Gorilla.objects.create(name='Alpha Portal')
    Gorilla.objects.create(name='Zebra Portal Build')
    Gorilla.objects.create(name='Build Notes')

    queryset = Glue.choices(
        Gorilla.objects.order_by('name'),
        search_fields=('name',),
    )

    assert _load_labels(queryset, search='portal build') == [
        'Zebra Portal Build',
        'Alpha Portal',
        'Build Notes',
    ]


def test_single_word_search_across_multiple_fields_prefers_both_then_field_order() -> None:
    Gorilla.objects.create(name='Alpha', description='Kong fighter')
    Gorilla.objects.create(name='Kong', description='Heavyweight')
    Gorilla.objects.create(name='Kong', description='King Kong')

    queryset = Glue.choices(
        Gorilla.objects.order_by('name', 'description'),
        search_fields=('name', 'description'),
        fields=('description',),
    )

    request = RequestFactory().get('/page/')
    result = GlueRelatedModelChoices(queryset).load(search='kong', request=request)
    pairs = [(item['label'], item['obj']['description']) for item in result['results']]

    assert pairs == [
        ('Kong', 'King Kong'),
        ('Kong', 'Heavyweight'),
        ('Alpha', 'Kong fighter'),
    ]


def test_duplicate_words_do_not_double_count_hits() -> None:
    Gorilla.objects.create(name='Acme Corp', description='Acme Portal Build')
    Gorilla.objects.create(name='Acme Corp', description='Portal Rewrite')

    queryset = Glue.choices(
        Gorilla.objects.order_by('description'),
        search_fields=('name', 'description'),
        fields=('description',),
    )

    request = RequestFactory().get('/page/')
    result = GlueRelatedModelChoices(queryset).load(search='acme ACME portal', request=request)
    descriptions = [item['obj']['description'] for item in result['results']]

    assert descriptions == ['Acme Portal Build', 'Portal Rewrite']


def test_relevance_ranking_works_with_annotated_relation_fields_and_search_limit() -> None:
    acme = Gorilla.objects.create(name='Acme Corp')
    alpha = Gorilla.objects.create(name='Alpha Co')
    beta = Gorilla.objects.create(name='Beta Co')

    Fight.objects.create(name='Portal A', description='', red_corner=alpha, blue_corner=alpha)
    Fight.objects.create(name='Portal B', description='', red_corner=beta, blue_corner=beta)
    Fight.objects.create(name='Portal Rewrite', description='', red_corner=acme, blue_corner=acme)

    queryset = Glue.choices(
        Fight.objects.annotate(corner_name=F('red_corner__name')).order_by('corner_name', 'name'),
        search_fields=('corner_name', 'name'),
        search_limit=2,
    )

    assert _load_labels(queryset, search='acme portal') == ['Portal Rewrite', 'Portal A']


def test_whitespace_only_search_behaves_like_empty_search() -> None:
    Gorilla.objects.create(name='Beta')
    Gorilla.objects.create(name='Alpha')

    queryset = Glue.choices(
        Gorilla.objects.order_by('name'),
        search_fields=('name',),
    )

    assert _load_labels(queryset, search='   ') == ['Alpha', 'Beta']


def test_relevance_ranking_works_on_distinct_querysets() -> None:
    Gorilla.objects.create(name='Alpha', description='Portal')
    Gorilla.objects.create(name='Acme', description='Portal')

    queryset = Glue.choices(
        Gorilla.objects.distinct().order_by('name'),
        search_fields=('name', 'description'),
    )

    assert _load_labels(queryset, search='acme portal') == ['Acme', 'Alpha']


def test_primary_field_full_match_outranks_split_field_match() -> None:
    Gorilla.objects.create(name='Acme Corp', description='Portal Rewrite')
    Gorilla.objects.create(name='Acme Portal', description='Other')
    Gorilla.objects.create(name='Acme Portal', description='Acme Portal')

    queryset = Glue.choices(
        Gorilla.objects.order_by('name', 'description'),
        search_fields=('name', 'description'),
        fields=('description',),
    )

    request = RequestFactory().get('/page/')
    result = GlueRelatedModelChoices(queryset).load(search='acme portal', request=request)
    pairs = [(item['label'], item['obj']['description']) for item in result['results']]

    assert pairs == [
        ('Acme Portal', 'Acme Portal'),
        ('Acme Portal', 'Other'),
        ('Acme Corp', 'Portal Rewrite'),
    ]


def test_search_words_preserves_non_ascii_casing_and_enforces_limits() -> None:
    from django_glue.glue.options.django.choices import _search_words  # noqa: PLC0415
    from django_glue.glue.options.django.constants import MAX_SEARCH_LENGTH, MAX_SEARCH_WORDS  # noqa: PLC0415

    assert _search_words('Straße Übung übung İzmir') == ['Straße', 'Übung', 'İzmir']
    assert len(_search_words(' '.join(f'word{index}' for index in range(MAX_SEARCH_WORDS + 5)))) == MAX_SEARCH_WORDS

    long_query = 'a' * (MAX_SEARCH_LENGTH - 2) + ' bcdef'
    assert _search_words(long_query) == ['a' * (MAX_SEARCH_LENGTH - 2), 'b']

    Gorilla.objects.create(name='Übung Straße')
    Gorilla.objects.create(name='Other')
    queryset = Glue.choices(Gorilla.objects.order_by('name'), search_fields=('name',))

    assert _load_labels(queryset, search='Übung') == ['Übung Straße']
    assert _load_labels(queryset, search='Straße') == ['Übung Straße']


def test_searchable_choices_rejects_distinct_on_fields() -> None:
    with pytest.raises(ValueError, match=r'distinct\(\*fields\)'):
        Glue.choices(
            Gorilla.objects.distinct('name'),
            search_fields=('name',),
        )
