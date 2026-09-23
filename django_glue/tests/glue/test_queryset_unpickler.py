from __future__ import annotations

import base64
import io
import pickle

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
from test_project.fight.models import Fight
from test_project.gorilla.models import Gorilla

FIGHT_PATH = 'test_project.fight.models.Fight'
GORILLA_PATH = 'test_project.gorilla.models.Gorilla'


class AllowlistedPickleMarker:
    """A non-model class used to exercise the public registration seam."""


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

    def test_oversized_continuation_is_refused_at_issuance(self):
        encoded = pickle_query(Fight.objects.all())

        with (
            override_settings(DJANGO_GLUE_MAX_QUERY_ENCODED_BYTES=len(encoded) - 1),
            pytest.raises(ValueError, match='DJANGO_GLUE_MAX_QUERY_ENCODED_BYTES'),
        ):
            pickle_query(Fight.objects.all())
