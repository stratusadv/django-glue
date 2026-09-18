from __future__ import annotations

import base64
import io
import pickle

import pytest
from django.test import TestCase

from django_glue.glue.objects.django.model.object import ModelGlue
from django_glue.glue.objects.django.queryset import QuerySetGlue
from django_glue.glue.options.django.choices import (
    QUERYSET_CHOICE_OPTIONS_ATTRIBUTE,
    QuerySetChoiceOptions,
)
from django_glue.glue.queryset_unpickler import QuerySetUnpickler, unpickle_query
from test_project.fight.models import Fight
from test_project.gorilla.models import Gorilla


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

        query = unpickle_query(encoded)

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

        query = unpickle_query(encoded)

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
        encoded = QuerySetGlue._encode_queryset_query(
            Fight.objects.filter(name__icontains='bout')
        )

        queryset = QuerySetGlue._decode_queryset_query(encoded)

        assert queryset.model is Fight
        assert queryset.query.model is Fight

    def test_choice_source_decodes_through_the_allowlist(self):
        encoded = base64.b64encode(
            pickle.dumps(Gorilla.objects.all().query)
        ).decode()

        deserialized = ModelGlue._deserialize_related_field_config(
            {'red_corner': {'encoded_choice_queryset': encoded}}
        )

        choice_queryset = deserialized['red_corner']['choice_queryset']
        assert choice_queryset.model is Gorilla
