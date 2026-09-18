from __future__ import annotations

from django.db.models import QuerySet
from django.test import TestCase

from django_glue.glue.objects.django.model.object import ModelGlue
from django_glue.glue.objects.django.queryset import QuerySetGlue
from test_project.fight.models import Fight


class TrackedQuerySet(QuerySet):
    """A custom QuerySet subclass whose method override must survive
    reconstruction through the introducing queryset."""

    filters_applied = 0

    def filter(self, *args, **kwargs):
        type(self).filters_applied += 1
        return super().filter(*args, **kwargs)


class QuerySetReconstructionTestCase(TestCase):
    def test_default_queryset_round_trips_through_its_class_path(self):
        queryset = Fight.objects.filter(name__icontains='bout')
        encoded = QuerySetGlue._encode_queryset_query(queryset)

        rebuilt = QuerySetGlue._decode_queryset_query(
            encoded,
            queryset_class_path=f'{type(queryset).__module__}.{type(queryset).__qualname__}',
        )

        assert type(rebuilt) is QuerySet
        assert rebuilt.model is Fight
        assert rebuilt.query.model is Fight
        assert list(rebuilt) == list(queryset)

    def test_custom_queryset_class_is_restored_through(self):
        queryset = TrackedQuerySet(model=Fight).filter(name__icontains='b')
        encoded = QuerySetGlue._encode_queryset_query(queryset)

        rebuilt = QuerySetGlue._decode_queryset_query(
            encoded,
            queryset_class_path=f'{type(queryset).__module__}.{type(queryset).__qualname__}',
        )
        before = TrackedQuerySet.filters_applied
        rebuilt.filter(name='x')
        after = TrackedQuerySet.filters_applied

        assert type(rebuilt) is TrackedQuerySet
        assert after == before + 1

    def test_unresolvable_class_path_fails_loudly(self):
        encoded = QuerySetGlue._encode_queryset_query(Fight.objects.all())

        with self.assertRaisesRegex(
            ValueError,
            'Cannot resolve queryset class',
        ):
            QuerySetGlue._decode_queryset_query(encoded, 'no.such.module.BogusQueryset')

    def test_non_queryset_class_path_fails_loudly(self):
        encoded = QuerySetGlue._encode_queryset_query(Fight.objects.all())

        with self.assertRaisesRegex(
            TypeError,
            'does not name a QuerySet subclass',
        ):
            QuerySetGlue._decode_queryset_query(encoded, 'test_project.fight.models.Fight')

    def test_identity_carries_the_queryset_class_path(self):
        queryset = Fight.objects.filter(name__icontains='bout')
        glue_object = QuerySetGlue(
            queryset,
            name='fights',
            fields=['name'],
        )

        assert glue_object.get_identity()['queryset_class_path'] == (
            f'{type(queryset).__module__}.{type(queryset).__qualname__}'
        )

    def test_choice_source_reconstructs_through_its_queryset_class(self):
        choice = TrackedQuerySet(model=Fight).filter(name__icontains='b')
        serialized = ModelGlue._serialize_related_field_config(
            {'red_corner': {'choice_queryset': choice}}
        )

        deserialized = ModelGlue._deserialize_related_field_config(serialized)
        rebuilt = deserialized['red_corner']['choice_queryset']

        assert type(rebuilt) is TrackedQuerySet
        assert rebuilt.query.model is Fight
        assert list(rebuilt) == list(choice)
