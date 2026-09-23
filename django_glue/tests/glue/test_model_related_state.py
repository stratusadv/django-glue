import json
from types import SimpleNamespace

import pytest
from django.test import RequestFactory, TestCase

from django_glue import Glue
from django_glue.access import GlueAccess
from django_glue.exceptions import GlueModelInstanceNotFoundError
from django_glue.glue.attributes import (
    BoundGlueAttribute,
    GlueAttributeKind,
    GlueValueRole,
)
from django_glue.glue.objects.django.form.object import FormGlue
from django_glue.glue.objects.django.model.object import ModelGlue
from django_glue.glue.objects.django.queryset import QuerySetGlue
from django_glue.glue.policy import GluePolicy
from django_glue.resolver.attribute_call.context import AttributeCallRequestContext
from django_glue.resolver.attribute_call.resolver import GlueAttributeCallResolver
from django_glue.tests.conftest import MockSession
from django_glue.tests.glue.addressed_rows import addressed_row_entries
from django_glue.tests.glue.test_refresh import request_entry
from test_project.fight.models import Fight
from test_project.gorilla.models import Gorilla, Skill
from test_project.test_forms import TestModelForm as GorillaModelForm


def request_with_session(session_key='test-session'):
    return SimpleNamespace(session=SimpleNamespace(session_key=session_key), FILES={})


class RelatedStateTestCase(TestCase):
    def setUp(self):
        self.alpha = Gorilla.objects.create(name='Alpha', age=12)
        self.beta = Gorilla.objects.create(name='Beta', age=24)
        self.fight = Fight.objects.create(name='Bout', red_corner=self.alpha, blue_corner=self.beta)

    def _glue(self):
        glue_object = ModelGlue(self.fight, name='fight', access=GlueAccess.CHANGE, fields=['name', 'red_corner', 'blue_corner'])
        glue_object.request = request_with_session()

        return glue_object

    def test_flat_relation_state_keeps_the_foreign_key(self):
        glue_object = self._glue()
        state = glue_object.state

        self.assertEqual(state['red_corner']['value'], self.alpha.pk)

        glue_object._load_client_state({
            'name': state['name']['value'],
            'red_corner': state['red_corner']['value'],
            'blue_corner': state['blue_corner']['value'],
        })

        self.assertEqual(glue_object.instance.red_corner_id, self.alpha.pk)
        self.assertEqual(glue_object.state['red_corner']['value'], self.alpha.pk)

    def test_flat_relation_state_applies_raw_identity(self):
        glue_object = self._glue()

        glue_object._load_client_state({'red_corner': self.beta.pk})

        self.assertEqual(glue_object.instance.red_corner_id, self.beta.pk)
        self.assertEqual(glue_object.state['red_corner']['value'], self.beta.pk)

    def test_plain_value_state_still_applies(self):
        glue_object = self._glue()

        glue_object._load_client_state({'red_corner': self.beta.pk})

        self.assertEqual(glue_object.instance.red_corner_id, self.beta.pk)

    def test_null_value_clears_the_relation(self):
        glue_object = self._glue()

        glue_object._load_client_state({'blue_corner': None})

        self.assertIsNone(glue_object.instance.blue_corner_id)

    def test_explicit_editable_projection_controls_model_updates(self):
        glue_object = ModelGlue(
            self.alpha,
            name='alpha',
            access=GlueAccess.CHANGE,
            fields=['name', 'description'],
            editable=['name'],
        )

        glue_object._load_client_state({
            'name': 'Updated',
            'description': 'Not admitted',
        })

        assert glue_object.instance.name == 'Updated'
        assert glue_object.instance.description == ''

    def test_model_definitions_stage_editable_drafts(self):
        glue_object = ModelGlue(
            self.alpha,
            name='alpha',
            access=GlueAccess.CHANGE,
            fields=['name', 'created_at'],
            editable=['name'],
        )
        name_definition = glue_object._attribute_registry.get('name')
        created_definition = glue_object._attribute_registry.get('created_at')

        assert name_definition is not None
        assert created_definition is not None
        assert name_definition.value_role == GlueValueRole.EDITABLE_STATE
        assert created_definition.value_role == GlueValueRole.DERIVED_OUTPUT

        name_attribute = BoundGlueAttribute(
            definition=name_definition,
            owner=glue_object,
        )
        created_attribute = BoundGlueAttribute(
            definition=created_definition,
            owner=glue_object,
        )
        name_attribute.apply_update('Draft')

        assert name_attribute.get() == 'Draft'
        assert glue_object.instance.name == 'Alpha'
        with pytest.raises(TypeError, match='does not accept client updates'):
            created_attribute.apply_update(None)

    def test_model_editable_projection_validates_its_boundary(self):
        with pytest.raises(ValueError, match='must be exposed'):
            ModelGlue(
                self.alpha,
                name='alpha',
                access=GlueAccess.CHANGE,
                fields=['name'],
                editable=['description'],
            )

        with pytest.raises(ValueError, match='concrete Django-editable'):
            ModelGlue(
                self.alpha,
                name='alpha',
                access=GlueAccess.CHANGE,
                fields=['created_at'],
                editable=['created_at'],
            )

    def test_model_editable_projection_is_signed_and_revalidated(self):
        glue_object = ModelGlue(
            self.alpha,
            name='alpha',
            access=GlueAccess.CHANGE,
            fields=['name', 'description'],
            editable=['name'],
        )
        glue_object.request = request_with_session()

        policy = glue_object.policy
        reconstructed = ModelGlue._reconstruct_from_policy(policy)

        assert policy.identity['editable'] == ('name',)
        assert reconstructed.editable == ('name',)
        assert set(reconstructed._included_fields) == {'id', 'name', 'description'}

    def test_model_default_form_is_an_addressed_child(self):
        glue_object = ModelGlue(
            self.alpha,
            name='alpha',
            access=GlueAccess.CHANGE,
            fields=['name'],
            form=GorillaModelForm(instance=self.alpha),
        )
        glue_object.request = request_with_session()

        definition = glue_object._attribute_registry.get('form')
        children = glue_object._bind_children()

        assert definition is not None
        assert definition.kind == GlueAttributeKind.CHILD
        assert definition.expected_type is FormGlue
        assert len(children) == 1
        assert children[0].path == 'form'
        assert isinstance(children[0].glue_object, FormGlue)
        assert children[0].glue_object.form.instance is self.alpha

        policy = glue_object.policy

        assert policy.children['form'] == children[0].address
        assert 'form' not in policy.attributes
        assert all(isinstance(attribute, str) for attribute in policy.attributes)

    def test_model_named_forms_are_children_under_explicit_namespace(self):
        glue_object = ModelGlue(
            self.alpha,
            name='alpha',
            access=GlueAccess.CHANGE,
            fields=['name'],
            forms={
                'edit': GorillaModelForm(instance=self.alpha),
                'review': GorillaModelForm(instance=self.alpha),
            },
        )

        definitions = glue_object._attribute_registry
        glue_object.request = request_with_session()
        children = glue_object._bind_children()

        assert definitions.get('forms').kind == GlueAttributeKind.NAMESPACE
        assert definitions.get('forms.edit').kind == GlueAttributeKind.CHILD
        assert definitions.get('forms.review').kind == GlueAttributeKind.CHILD
        assert tuple(child.path for child in children) == (
            'forms.edit',
            'forms.review',
        )
        assert all(
            isinstance(child.glue_object, FormGlue)
            for child in children
        )

    def test_model_shortcut_can_construct_unbound_child(self):
        glue_object = Glue.model(
            target=self.alpha,
            fields=['name'],
        )

        assert isinstance(glue_object, ModelGlue)
        assert not glue_object.is_bound
        assert glue_object.name == 'model'

    def test_model_flat_relation_name_does_not_introduce_child(self):
        glue_object = ModelGlue(
            self.fight,
            name='fight',
            access=GlueAccess.VIEW,
            fields=['name', 'red_corner'],
        )
        glue_object.request = request_with_session()

        assert glue_object._attribute_registry.get('red_corner') is not None
        assert glue_object._attribute_registry.get('red_corner').kind == GlueAttributeKind.VALUE
        assert glue_object._attribute_registry.get('red_corner__id') is None

    def test_projected_relation_is_an_addressed_child(self):
        glue_object = ModelGlue(
            self.fight,
            name='fight',
            access=GlueAccess.VIEW,
            fields=['red_corner__id', 'red_corner__name'],
        )
        glue_object.request = request_with_session()

        red_corner = glue_object._attribute_registry.get('red_corner')
        red_corner_id = glue_object._attribute_registry.get('red_corner_id')

        assert red_corner is not None
        assert red_corner.kind == GlueAttributeKind.CHILD
        assert red_corner.expected_type is ModelGlue
        assert red_corner.is_nullable is False
        assert red_corner_id is not None
        assert red_corner_id.kind == GlueAttributeKind.VALUE

        children = glue_object._bind_children()
        assert len(children) == 1
        assert children[0].path == 'red_corner'
        assert children[0].address.startswith(f'{glue_object.address}.')
        assert isinstance(children[0].glue_object, ModelGlue)
        assert children[0].glue_object.instance is self.alpha
        assert children[0].glue_object.request is glue_object.request
        assert set(children[0].glue_object._included_fields) == {'id', 'name'}

    def test_projected_relation_raw_identity_stays_editable(self):
        glue_object = ModelGlue(
            self.fight,
            name='fight',
            access=GlueAccess.CHANGE,
            fields=['red_corner__id', 'red_corner__name'],
        )
        glue_object.request = request_with_session()

        identity_definition = glue_object._attribute_registry.get('red_corner_id')
        assert identity_definition.value_role == GlueValueRole.EDITABLE_STATE

        identity = BoundGlueAttribute(
            definition=identity_definition,
            owner=glue_object,
        )
        assert identity.get() == self.alpha.pk
        identity.apply_update(self.beta.pk)
        assert glue_object._editable_draft['red_corner_id'] == self.beta.pk

    def test_projected_nullable_relation_resolves_to_absent(self):
        glue_object = ModelGlue(
            self.fight,
            name='fight',
            access=GlueAccess.VIEW,
            fields=['winner__id', 'winner__name'],
        )
        glue_object.request = request_with_session()

        winner = glue_object._attribute_registry.get('winner')
        assert winner is not None
        assert winner.kind == GlueAttributeKind.CHILD
        assert winner.is_nullable is True
        assert glue_object._bind_children() == ()

        self.fight.winner = self.alpha
        self.fight.save()
        children = glue_object._bind_children()
        assert len(children) == 1
        assert children[0].path == 'winner'
        assert children[0].glue_object.instance is self.alpha

    def test_projected_non_nullable_child_not_reevaluated_when_live(self):
        glue_object = ModelGlue(
            self.fight,
            name='fight',
            access=GlueAccess.VIEW,
            fields=['red_corner__id', 'red_corner__name'],
        )
        glue_object.request = request_with_session()

        children = glue_object._bind_children(
            live_children={'red_corner': 'model-address.existing'},
        )

        assert len(children) == 1
        assert children[0].address == 'model-address.existing'
        assert children[0].glue_object is None

    def test_projected_relation_editable_root_maps_to_raw_identity(self):
        glue_object = ModelGlue(
            self.fight,
            name='fight',
            access=GlueAccess.CHANGE,
            fields=['red_corner__id', 'red_corner__name'],
            editable=['red_corner'],
        )

        assert glue_object.editable == ('red_corner_id',)

    def test_projected_many_to_many_is_an_addressed_collection_child(self) -> None:
        grappling = Skill.objects.create(name='Grappling')
        climbing = Skill.objects.create(name='Climbing')
        self.alpha.skills.add(grappling, climbing)
        glue_object = ModelGlue(
            self.alpha,
            name='alpha',
            access=GlueAccess.VIEW,
            fields=['skills__id', 'skills__name'],
        )
        glue_object.request = request_with_session()

        definition = glue_object._attribute_registry.get('skills')
        assert definition is not None
        assert definition.kind == GlueAttributeKind.CHILD
        assert definition.expected_type is QuerySetGlue
        assert definition.is_nullable is False
        assert set(glue_object.state['skills_ids']['value']) == {
            grappling.pk,
            climbing.pk,
        }

        children = glue_object._bind_children()
        assert len(children) == 1
        assert children[0].path == 'skills'
        assert children[0].address.startswith(f'{glue_object.address}.')
        assert isinstance(children[0].glue_object, QuerySetGlue)
        assert set(children[0].glue_object.queryset.values_list('pk', flat=True)) == {
            grappling.pk,
            climbing.pk,
        }
        assert set(children[0].glue_object._included_fields) == {'id', 'name'}

    def test_projected_reverse_relation_is_an_addressed_collection_child(self) -> None:
        glue_object = ModelGlue(
            self.alpha,
            name='alpha',
            access=GlueAccess.VIEW,
            fields=['fights_as_red_corner__id', 'fights_as_red_corner__name'],
        )
        glue_object.request = request_with_session()

        definition = glue_object._attribute_registry.get('fights_as_red_corner')
        assert definition is not None
        assert definition.kind == GlueAttributeKind.CHILD
        assert definition.expected_type is QuerySetGlue
        assert definition.is_nullable is False
        assert glue_object.state['fights_as_red_corner_ids']['value'] == (
            self.fight.pk,
        )

        children = glue_object._bind_children()
        assert len(children) == 1
        assert children[0].path == 'fights_as_red_corner'
        assert isinstance(children[0].glue_object, QuerySetGlue)
        assert list(children[0].glue_object.queryset) == [self.fight]
        assert set(children[0].glue_object._included_fields) == {'id', 'name'}

    def test_projected_many_to_many_survives_policy_reconstruction(self) -> None:
        grappling = Skill.objects.create(name='Grappling')
        self.alpha.skills.add(grappling)
        glue_object = ModelGlue(
            self.alpha,
            name='alpha',
            access=GlueAccess.VIEW,
            fields=['skills__id', 'skills__name'],
        )
        glue_object.request = request_with_session()

        policy = glue_object.policy
        reconstructed = ModelGlue._reconstruct_from_policy(policy)
        reconstructed.request = request_with_session()

        assert policy.identity['projected_fields'] == (
            'skills__id',
            'skills__name',
        )
        definition = reconstructed._attribute_registry.get('skills')
        assert definition is not None
        assert definition.kind == GlueAttributeKind.CHILD
        assert definition.expected_type is QuerySetGlue
        children = reconstructed._bind_children()
        assert len(children) == 1
        assert isinstance(children[0].glue_object, QuerySetGlue)
        assert list(children[0].glue_object.queryset) == [grappling]


class QuerySetGlueProjectedRelationChildrenTestCase(TestCase):
    def setUp(self):
        self.alpha = Gorilla.objects.create(name='Alpha', age=12)
        self.beta = Gorilla.objects.create(name='Beta', age=24)
        self.gamma = Gorilla.objects.create(name='Gamma', age=36)
        self.fight_one = Fight.objects.create(
            name='Fight One',
            red_corner=self.alpha,
            blue_corner=self.beta,
        )
        self.fight_two = Fight.objects.create(
            name='Fight Two',
            red_corner=self.alpha,
            blue_corner=self.gamma,
        )

    def _glue(self, fields):
        glue_object = QuerySetGlue(
            Fight.objects.filter(pk__in=[self.fight_one.pk, self.fight_two.pk]),
            name='fights',
            access=GlueAccess.VIEW,
            fields=fields,
        )
        glue_object.request = request_with_session()

        return glue_object

    def test_rows_share_one_child_per_related_object(self):
        glue_object = self._glue(
            fields=['name', 'red_corner__id', 'red_corner__name']
        )

        children = glue_object._bind_relation_children(
            [self.fight_one, self.fight_two],
            owner_address='fights-address',
        )

        assert len(children) == 1
        assert children[0].path == f'red_corner.{self.alpha.pk}'
        assert isinstance(children[0].glue_object, ModelGlue)
        assert children[0].glue_object.instance is self.alpha
        assert children[0].glue_object.request is glue_object.request
        assert set(children[0].glue_object._included_fields) == {'id', 'name'}

    def test_row_policies_reference_the_collection_owned_relation_child(self):
        glue_object = self._glue(
            fields=['name', 'red_corner__id', 'red_corner__name']
        )

        result = glue_object.query_with_params()
        row_policies = [
            GluePolicy.from_token(row['policy_token'])
            for row in addressed_row_entries(glue_object, result)
        ]
        relation_address = glue_object.policy.children[
            f'red_corner.{self.alpha.pk}'
        ]
        serialized = glue_object._serialized_child_entries()

        assert all(
            policy.children['red_corner'] == relation_address
            for policy in row_policies
        )
        assert sum(
            entry['address'] == relation_address
            for entry in serialized
        ) == 1

    def test_projected_to_many_rows_reference_collection_owned_querysets(self):
        skill = Skill.objects.create(name='Grappling')
        self.alpha.skills.add(skill)
        glue_object = QuerySetGlue(
            Gorilla.objects.filter(pk=self.alpha.pk),
            name='gorillas',
            access=GlueAccess.VIEW,
            fields=['name', 'skills__id', 'skills__name'],
        )
        glue_object.request = request_with_session()

        result = glue_object.query_with_params()
        row_policy = GluePolicy.from_token(addressed_row_entries(glue_object, result)[0]['policy_token'])
        relation_address = glue_object.policy.children[
            f'skills.{self.alpha.pk}'
        ]
        serialized = glue_object._serialized_child_entries()
        relation_entry = next(
            entry
            for entry in serialized
            if entry['address'] == relation_address
        )

        assert row_policy.children['skills'] == relation_address
        assert GluePolicy.from_token(
            relation_entry['policy_token']
        ).namespace == 'querySet'

    def test_row_exposes_raw_identity_not_the_shared_child(self):
        glue_object = self._glue(
            fields=['name', 'red_corner__id', 'red_corner__name']
        )

        assert 'red_corner_id' in glue_object._included_fields
        assert 'red_corner' not in glue_object._included_fields

    def test_projected_fields_survive_policy_reconstruction(self) -> None:
        glue_object = self._glue(
            fields=['name', 'red_corner__id', 'red_corner__name']
        )

        policy = glue_object.policy
        reconstructed = QuerySetGlue._reconstruct_from_policy(policy)

        assert policy.identity['projected_fields'] == (
            'red_corner__id',
            'red_corner__name',
        )
        assert reconstructed._projected_relations == (
            ('red_corner', ('id', 'name')),
        )

    def test_distinct_related_objects_get_distinct_canonical_addresses(self):
        glue_object = self._glue(
            fields=['red_corner__id', 'blue_corner__id']
        )

        children = glue_object._bind_relation_children(
            [self.fight_one, self.fight_two],
            owner_address='fights-address',
        )

        assert len(children) == 3
        asserted = {children[0].address, children[1].address, children[2].address}
        assert len(asserted) == 3
        assert {child.glue_object.instance for child in children} == {
            self.alpha,
            self.beta,
            self.gamma,
        }
        assert all(child.glue_object.namespace == 'model' for child in children)

    def test_same_related_object_yields_identical_address_across_calls(self):
        glue_object = self._glue(
            fields=['red_corner__id', 'red_corner__name']
        )

        first = glue_object._bind_relation_children(
            [self.fight_one],
            owner_address='fights-address',
        )
        second = glue_object._bind_relation_children(
            [self.fight_one, self.fight_two],
            owner_address='fights-address',
        )

        assert len(first) == 1
        assert len(second) == 1
        assert first[0].address == second[0].address
        assert second[0].address.startswith('fights-address.')

    def test_nullable_relation_rows_without_the_object_contribute_nothing(self):
        fight_with_winner = Fight.objects.create(
            name='Decided',
            red_corner=self.alpha,
            blue_corner=self.beta,
            winner=self.alpha,
        )
        fight_without_winner = Fight.objects.create(
            name='Open',
            red_corner=self.beta,
            blue_corner=self.alpha,
        )
        glue_object = QuerySetGlue(
            Fight.objects.filter(pk__in=[fight_with_winner.pk, fight_without_winner.pk]),
            name='fights',
            access=GlueAccess.VIEW,
            fields=['winner__id', 'winner__name'],
        )
        glue_object.request = request_with_session()

        children = glue_object._bind_relation_children(
            [fight_with_winner, fight_without_winner],
            owner_address='fights-address',
        )

        assert len(children) == 1
        assert children[0].glue_object.instance is self.alpha

    def test_reconstructed_row_restores_collection_owned_relation_references(self):
        glue_object = self._glue(
            fields=['name', 'red_corner__id', 'red_corner__name']
        )
        result = glue_object.query_with_params()
        row_policy = GluePolicy.from_token(addressed_row_entries(glue_object, result)[0]['policy_token'])
        relation_address = glue_object.policy.children[
            f'red_corner.{self.alpha.pk}'
        ]

        reconstructed = ModelGlue._reconstruct_from_policy(row_policy)
        reconstructed.request = request_with_session()
        reconstructed._address = row_policy.address

        assert row_policy.children == {'red_corner': relation_address}
        assert reconstructed.children == row_policy.children
        relation_child = reconstructed._bound_children[0]
        assert relation_child.path == 'red_corner'
        assert relation_child.address == relation_address
        assert relation_child.glue_object is None

    def test_reconstructed_to_many_row_restores_collection_owned_queryset_reference(self):
        skill = Skill.objects.create(name='Grappling')
        self.alpha.skills.add(skill)
        glue_object = QuerySetGlue(
            Gorilla.objects.filter(pk=self.alpha.pk),
            name='gorillas',
            access=GlueAccess.VIEW,
            fields=['name', 'skills__id', 'skills__name'],
        )
        glue_object.request = request_with_session()
        result = glue_object.query_with_params()
        row_policy = GluePolicy.from_token(addressed_row_entries(glue_object, result)[0]['policy_token'])
        relation_address = glue_object.policy.children[
            f'skills.{self.alpha.pk}'
        ]

        reconstructed = ModelGlue._reconstruct_from_policy(row_policy)
        reconstructed.request = request_with_session()
        reconstructed._address = row_policy.address

        assert reconstructed.children == row_policy.children
        relation_child = reconstructed._bound_children[0]
        assert relation_child.path == 'skills'
        assert relation_child.address == relation_address
        assert relation_child.glue_object is None

    def test_row_attribute_call_on_projected_row_is_quiet_about_children(self):
        glue_object = self._glue(
            fields=['name', 'red_corner__id', 'red_corner__name']
        )
        result = glue_object.query_with_params()
        row_policy = GluePolicy.from_token(addressed_row_entries(glue_object, result)[0]['policy_token'])
        context = AttributeCallRequestContext.model_construct(
            request=request_with_session(),
            target_glue_policy=row_policy,
            target_glue_updates={},
            target_attribute_name=None,
            target_attribute_call_kwargs={},
        )
        reconstructed = ModelGlue.from_attribute_call_resolver_context(context)

        entry, introduced = reconstructed.process_attribute_call(context)

        assert introduced == []
        assert 'policy_token' not in entry


class GlueFieldsSelectionTestCase(TestCase):
    def setUp(self):
        self.alpha = Gorilla.objects.create(name='Alpha', age=12)
        self.beta = Gorilla.objects.create(name='Beta', age=24)
        self.fight = Fight.objects.create(name='Bout', red_corner=self.alpha, blue_corner=self.beta)

    def test_selection_normalizes_to_canonical_paths(self):
        assert Glue.fields('id', 'name', red_corner=('id', 'name')) == (
            'id', 'name', 'red_corner__id', 'red_corner__name',
        )

    def test_nested_selection_prefixes_deeper_paths(self):
        assert Glue.fields('name', red_corner=Glue.fields('name', skills=('name',))) == (
            'name', 'red_corner__name', 'red_corner__skills__name',
        )

    def test_selection_and_ordinary_list_project_identically(self):
        helper = ModelGlue(
            self.fight,
            name='fight',
            access=GlueAccess.VIEW,
            fields=Glue.fields('name', red_corner=('name',)),
        )
        ordinary = ModelGlue(
            self.fight,
            name='fight',
            access=GlueAccess.VIEW,
            fields=['name', 'red_corner__name'],
        )

        assert helper._included_fields == ordinary._included_fields
        assert helper._projected_field_paths == ordinary._projected_field_paths

    def test_selection_is_accepted_by_exclude(self):
        glue_object = ModelGlue(
            self.fight,
            name='fight',
            access=GlueAccess.VIEW,
            fields=['name', 'red_corner'],
            exclude=Glue.fields('red_corner'),
        )

        assert 'red_corner' not in glue_object._included_fields

    def test_relation_value_must_be_a_sequence_of_names(self):
        with pytest.raises(TypeError, match='not a string'):
            Glue.fields(red_corner='name')
        with pytest.raises(TypeError, match='non-empty strings'):
            Glue.fields('')


class ProjectedRelationCreationAccessTestCase(TestCase):
    """Projected relation children receive exactly ADD, never implicit
    CHANGE or DELETE, and never from an unsaved owner (state-model.md §4,
    ADR 009)."""

    def setUp(self):
        self.alpha = Gorilla.objects.create(name='Alpha', age=12)
        self.grappling = Skill.objects.create(name='Grappling')

    def _model(self, access):
        glue_object = ModelGlue(
            self.alpha,
            name='alpha',
            access=access,
            fields=['skills__id', 'skills__name'],
        )
        glue_object.request = request_with_session()
        return glue_object

    def test_view_model_projected_to_many_child_stays_view(self):
        skills = self._model(GlueAccess.VIEW)._bind_children()[0].glue_object

        assert skills.access == GlueAccess.VIEW

    def test_change_model_projected_to_many_child_gets_exactly_add(self):
        skills = self._model(GlueAccess.CHANGE)._bind_children()[0].glue_object

        assert isinstance(skills, QuerySetGlue)
        assert skills.access == GlueAccess.ADD

    def test_unsaved_model_owner_relation_stays_view(self):
        glue_object = ModelGlue(
            Gorilla(name='Unsaved', age=5),
            name='alpha',
            access=GlueAccess.ADD,
            fields=['skills__id', 'skills__name'],
        )
        glue_object.request = request_with_session()

        skills = glue_object._bind_children()[0].glue_object

        assert skills.access == GlueAccess.VIEW

    def test_to_one_relation_child_stays_view_for_change_owner(self):
        fight = Fight.objects.create(
            name='Bout',
            red_corner=self.alpha,
            blue_corner=self.alpha,
        )
        glue_object = ModelGlue(
            fight,
            name='fight',
            access=GlueAccess.CHANGE,
            fields=['red_corner__id', 'red_corner__name'],
        )
        glue_object.request = request_with_session()

        child = glue_object._bind_children()[0].glue_object

        assert isinstance(child, ModelGlue)
        assert child.access == GlueAccess.VIEW

    def test_add_relation_child_rows_are_view_and_drafts_are_add(self):
        """Expose existing members as VIEW rows while a new() draft is
        create-in-progress on the same ADD relation child."""
        self.alpha.skills.add(self.grappling)
        skills = self._model(GlueAccess.ADD)._bind_children()[0].glue_object
        skills.request = request_with_session()

        row_policy = skills._row_glue(self.grappling).policy
        draft_policy = skills._row_glue(Skill(name='Draft')).policy

        assert skills.access == GlueAccess.ADD
        assert row_policy.access == GlueAccess.VIEW
        assert row_policy.identity['target_pk'] == self.grappling.pk
        assert draft_policy.access == GlueAccess.ADD
        assert draft_policy.identity['target_pk'] is None


class RelationDraftAttachTestCase(TestCase):
    """A draft from ``relation.new()`` saves and attaches to the exact signed
    relation in one transaction (state-model.md §4 "Relation membership")."""

    def setUp(self):
        self.alpha = Gorilla.objects.create(name='Alpha', age=12)
        self.beta = Gorilla.objects.create(name='Beta', age=24)
        self.request = request_with_session()

    def _relation_policy(self, fields):
        glue_object = ModelGlue(self.alpha, name='alpha', access=GlueAccess.CHANGE, fields=fields)
        glue_object.request = self.request
        relation = glue_object._bind_children()[0].glue_object
        relation.request = self.request
        return relation.policy

    def _new_draft(self, relation_policy, initial):
        entry, introduced, _successor = request_entry(
            QuerySetGlue, relation_policy, self.request, attribute='new', kwargs={'initial': initial},
        )
        draft_entry = next(item for item in introduced if item['address'] == entry['result'])
        return GluePolicy.from_token(draft_entry['policy_token'])

    def _save(self, draft_policy):
        entry, _introduced, successor = request_entry(
            ModelGlue, draft_policy, self.request, attribute='save',
        )
        return entry['result'], successor

    def test_many_to_many_draft_is_added_to_the_owner_relation(self):
        relation_policy = self._relation_policy(['skills__id', 'skills__name'])
        draft_policy = self._new_draft(relation_policy, {'name': 'Foraging'})

        result, successor = self._save(draft_policy)

        assert result['success'] is True
        assert list(self.alpha.skills.values_list('name', flat=True)) == ['Foraging']
        assert successor.identity['target_pk'] == Skill.objects.get(name='Foraging').pk
        assert 'relation' not in successor.identity

    def test_reverse_foreign_key_draft_gets_the_signed_owner(self):
        relation_policy = self._relation_policy([
            'fights_as_red_corner__name',
            'fights_as_red_corner__description',
            'fights_as_red_corner__red_corner',
            'fights_as_red_corner__blue_corner',
        ])
        draft_policy = self._new_draft(
            relation_policy,
            {
                'name': 'Rematch',
                'description': 'Round two',
                'red_corner': self.beta.pk,
                'blue_corner': self.beta.pk,
            },
        )

        result, _successor = self._save(draft_policy)

        assert result['success'] is True
        fight = Fight.objects.get(name='Rematch')
        assert fight.red_corner == self.alpha

    def test_invalid_draft_attaches_nothing(self):
        relation_policy = self._relation_policy(['skills__id', 'skills__name'])
        draft_policy = self._new_draft(relation_policy, {'name': ''})

        result, _successor = self._save(draft_policy)

        assert result['success'] is False
        assert not Skill.objects.exists()
        assert not self.alpha.skills.exists()

    def test_relation_refreshed_in_the_same_batch_sees_the_new_member(self):
        relation_policy = self._relation_policy(['skills__id', 'skills__name'])
        draft_policy = self._new_draft(relation_policy, {'name': 'Foraging'})
        request = RequestFactory().post('/__dg__/callable_attribute/', data={'objects': json.dumps([
            {
                'address': draft_policy.address,
                'policy_token': draft_policy.token,
                'call': {'attribute': 'save', 'kwargs': {}},
            },
            {'address': relation_policy.address, 'policy_token': relation_policy.token},
        ])})
        request.session = MockSession()

        objects = json.loads(GlueAttributeCallResolver.as_view()(request).content)['objects']

        relation_entry = next(item for item in objects if item['address'] == relation_policy.address)
        skill = Skill.objects.get(name='Foraging')
        assert relation_entry['computed_data']['items'] == [f'{relation_policy.address}[{skill.pk}]']

    def test_deleted_owner_fails_the_save(self):
        relation_policy = self._relation_policy(['skills__id', 'skills__name'])
        draft_policy = self._new_draft(relation_policy, {'name': 'Foraging'})
        self.alpha.delete()

        with pytest.raises(GlueModelInstanceNotFoundError):
            self._save(draft_policy)

        assert not Skill.objects.exists()
