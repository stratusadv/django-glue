from __future__ import annotations

import base64
import datetime
import io
import pickle
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from unittest.mock import patch

import pytest
from django.test import TestCase, override_settings

from django_glue.glue.objects.django.model.object import ModelGlue
from django_glue.glue.objects.django.queryset import QuerySetGlue
from django_glue.glue.options.django.choices import (
    QUERYSET_CHOICE_OPTIONS_ATTRIBUTE,
    QuerySetChoiceOptions,
)
from django_glue.glue.queryset_unpickler import QuerySetUnpickler, pickle_query, unpickle_query
from test_project.fight.choices import FightStatusChoices
from test_project.fight.models import Fight
from test_project.gorilla.models import Gorilla

FIGHT_PATH = 'test_project.fight.models.Fight'
GORILLA_PATH = 'test_project.gorilla.models.Gorilla'


class AllowlistedPickleMarker:
    """A non-model class used to exercise the public registration seam."""


class UnlistedFilterValue(str):
    """An application value type a filter can carry that the allowlist refuses."""


def _global_payload(module: str, name: str) -> bytes:
    return f'c{module}\n{name}\n.'.encode()


def _load(payload: bytes):
    return QuerySetUnpickler(io.BytesIO(payload)).load()


class QuerySetUnpicklerTestCase(TestCase):
    def test_round_trips_a_framework_queryset(self):
        encoded = base64.b64encode(
            pickle.dumps(
                Fight.objects.filter(name__icontains='bout').query
            )
        ).decode()

        query = unpickle_query(encoded, FIGHT_PATH)

        assert query.model is Fight
        assert str(query)  # a fully reconstructed Query is functional

    def test_allows_an_app_registry_model(self):
        assert _load(_global_payload('test_project.fight.models', 'Fight')) is Fight

    def test_allows_standard_query_value_types(self):
        for module, name, expected in (
            ('datetime', 'date', datetime.date),
            ('datetime', 'datetime', datetime.datetime),
            ('datetime', 'time', datetime.time),
            ('datetime', 'timedelta', datetime.timedelta),
            ('datetime', 'timezone', datetime.timezone),
            ('decimal', 'Decimal', Decimal),
            ('uuid', 'UUID', UUID),
        ):
            assert _load(_global_payload(module, name)) is expected

    def test_allows_the_choice_source_continuation_carrier(self):
        queryset = Fight.objects.all()
        setattr(
            queryset.query,
            QUERYSET_CHOICE_OPTIONS_ATTRIBUTE,
            QuerySetChoiceOptions(
                search_fields=(),
                fields=('name',),
                search_limit=100,
            ),
        )
        encoded = base64.b64encode(pickle.dumps(queryset.query)).decode()

        query = unpickle_query(encoded, FIGHT_PATH)

        assert query.model is Fight
        options = getattr(query, QUERYSET_CHOICE_OPTIONS_ATTRIBUTE)
        assert options.fields == ('name',)

    def test_rejects_a_standard_library_class(self):
        with pytest.raises(pickle.UnpicklingError, match='outside the queryset allowlist'):
            _load(_global_payload('os', 'system'))

    def test_rejects_a_django_class_outside_the_orm_namespace(self):
        with pytest.raises(pickle.UnpicklingError, match='outside the queryset allowlist'):
            _load(_global_payload('django.views.generic', 'View'))

    def test_rejects_an_unregistered_application_class(self):
        with pytest.raises(pickle.UnpicklingError, match='outside the queryset allowlist'):
            _load(_global_payload(__name__, 'AllowlistedPickleMarker'))

    def test_register_admits_a_custom_lookup_or_expression(self):
        registered = f'{__name__}.AllowlistedPickleMarker'
        QuerySetUnpickler.register(registered)
        try:
            assert _load(_global_payload(__name__, 'AllowlistedPickleMarker')) is AllowlistedPickleMarker
        finally:
            QuerySetUnpickler._registered_qualified_names.discard(registered)


class QuerySetUnpicklerWiringTestCase(TestCase):
    def setUp(self):
        self.alpha = Gorilla.objects.create(name='Alpha', age=12)

    def test_queryset_continuation_decodes_through_the_allowlist(self):
        encoded = pickle_query(Fight.objects.filter(name__icontains='bout'))

        queryset = QuerySetGlue._decode_queryset_query(encoded, FIGHT_PATH)

        assert queryset.model is Fight
        assert queryset.query.model is Fight

    def test_datetime_filter_issues_a_queryset_continuation(self):
        cutoff = datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc)
        queryset = Gorilla.objects.filter(created_at__gte=cutoff)

        restored = unpickle_query(pickle_query(queryset), GORILLA_PATH)

        assert str(restored) == str(queryset.query)

    def test_choice_source_decodes_through_the_allowlist(self):
        encoded = pickle_query(Gorilla.objects.all())

        deserialized = ModelGlue._deserialize_choices(
            {'red_corner': {'encoded_queryset': encoded, 'model_class_path': GORILLA_PATH}}
        )

        choice_queryset = deserialized['red_corner']
        assert choice_queryset.model is Gorilla


class QuerySetContinuationBoundTestCase(TestCase):
    def test_oversized_continuation_is_refused_before_decoding(self):
        encoded = pickle_query(Fight.objects.all())

        with (
            override_settings(DJANGO_GLUE_MAX_QUERY_ENCODED_BYTES=len(encoded) - 1),
            patch('django_glue.glue.queryset_unpickler.base64.b64decode') as decode,
            pytest.raises(pickle.UnpicklingError, match='DJANGO_GLUE_MAX_QUERY_ENCODED_BYTES'),
        ):
            unpickle_query(encoded, FIGHT_PATH)
        decode.assert_not_called()

    def test_continuation_for_another_model_is_refused(self):
        with pytest.raises(pickle.UnpicklingError, match='does not match the signed'):
            unpickle_query(pickle_query(Gorilla.objects.all()), FIGHT_PATH)

    def test_choices_member_in_a_filter_is_issued_as_its_plain_value(self):
        queryset = Fight.objects.filter(status=FightStatusChoices.IN_PROGRESS)

        query = unpickle_query(pickle_query(queryset), FIGHT_PATH)

        assert str(query) == str(queryset.query)

    def test_value_outside_the_allowlist_is_refused_at_issuance(self):
        queryset = Fight.objects.filter(name=UnlistedFilterValue('bout'))

        with pytest.raises(ValueError, match=f'{__name__}.UnlistedFilterValue'):
            pickle_query(queryset)

    def test_oversized_continuation_is_refused_at_issuance(self):
        encoded = pickle_query(Fight.objects.all())

        with (
            override_settings(DJANGO_GLUE_MAX_QUERY_ENCODED_BYTES=len(encoded) - 1),
            pytest.raises(ValueError, match='DJANGO_GLUE_MAX_QUERY_ENCODED_BYTES'),
        ):
            pickle_query(Fight.objects.all())


class RelatedModelInstanceFilterTestCase(TestCase):
    """A related filter holds the filter value as a model instance: the lookup
    normalizes ``rhs`` to the pk at construction, but ``@deconstructible``
    keeps the raw instance in ``_constructor_args``. Serializing that instance
    would carry its field values (tz-aware datetimes, loaded relations) into
    the signed query, and a tz-aware datetime pickles its ``ZoneInfo`` tzinfo
    through ``builtins.getattr`` — outside the closed allowlist."""

    def setUp(self):
        self.red = Gorilla.objects.create(name='Red', age=20)
        self.red.updated_at = datetime.datetime(
            2026, 1, 2, 3, 4, 5, tzinfo=ZoneInfo('America/Edmonton')
        )
        self.blue = Gorilla.objects.create(name='Blue', age=22)
        self.fight = Fight.objects.create(name='Rumble', red_corner=self.red, blue_corner=self.blue)

    def test_related_manager_queryset_issues_a_continuation(self):
        queryset = self.red.fights_as_red_corner.all()

        restored = unpickle_query(pickle_query(queryset), FIGHT_PATH)

        assert str(restored) == str(queryset.query)

    def test_related_filter_by_instance_issues_a_continuation(self):
        queryset = Fight.objects.filter(red_corner=self.red)

        restored = unpickle_query(pickle_query(queryset), FIGHT_PATH)

        assert str(restored) == str(queryset.query)

    def test_reverse_related_filter_by_instance_issues_a_continuation(self):
        queryset = Gorilla.objects.filter(fights_as_red_corner=self.fight)

        restored = unpickle_query(pickle_query(queryset), GORILLA_PATH)

        assert str(restored) == str(queryset.query)
