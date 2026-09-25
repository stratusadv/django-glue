"""Protocol admission and signed state snapshots (state-model.md §5, §10)."""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from typing import Any, ClassVar

import pytest
from django.test import TestCase, override_settings

from django_glue import Glue, GlueSerializerHandler, GlueSerializerRegistry
from django_glue.access import GlueAccess
from django_glue.exceptions import GlueAuthorizationError, GlueRequestError, GlueRequestErrorCode
from django_glue.glue.base import BaseGlue
from django_glue.glue.operation import GlueOperation, GlueOperationKind
from django_glue.glue.objects.django.form.object import FormGlue
from django_glue.glue.objects.django.model.object import ModelGlue
from django_glue.glue.policy import GluePolicy
from django_glue.resolver.attribute_call.context import AttributeCallRequestContext
from test_project.fight.models import Fight
from test_project.gorilla.models import Gorilla, Skill


def request_with_session(session_key='test-session'):
    return SimpleNamespace(session=SimpleNamespace(session_key=session_key), FILES={})


class AdmissionProbeGlue(BaseGlue):
    namespace = 'admissionProbe'

    value = Glue.attr('canonical', editable=True)
    other = Glue.attr('second', editable=True)
    number: int = Glue.attr(0, editable=True)

    @Glue.property
    def derived(self) -> str:
        return 'derived'

    @Glue.attr
    def echo(self) -> str:
        return self.value

    @Glue.attr
    def increment(self) -> int:
        return self.number + 1

    def __init__(self) -> None:
        super().__init__(name='admission-probe', access=GlueAccess.CHANGE)

    @classmethod
    def _reconstruct_from_policy(cls, policy: GluePolicy) -> AdmissionProbeGlue:
        _ = policy
        return cls()


class UpdateGuardedProbeGlue(AdmissionProbeGlue):
    namespace = 'updateGuardedProbe'
    operations: ClassVar[list[GlueOperation]] = []

    def is_authorized(self, request, operation: GlueOperation) -> bool:
        type(self).operations.append(operation)
        return not (operation.kind == GlueOperationKind.UPDATE and operation.attribute == 'other')


class DraftAuthorizationTestCase(TestCase):
    def setUp(self):
        UpdateGuardedProbeGlue.operations = []
        self.glue_object = UpdateGuardedProbeGlue()
        self.glue_object.request = request_with_session()

    def _call(self, updates):
        context = AttributeCallRequestContext.model_construct(
            request=self.glue_object.request,
            target_glue_policy=self.glue_object.policy,
            target_glue_updates=updates,
            target_attribute_name='echo',
            target_attribute_call_kwargs={},
            reintroduce=[],
        )
        return self.glue_object.process_attribute_call(context)

    def test_each_admitted_draft_is_authorized_with_its_path(self):
        entry, _introduced = self._call({'value': 'typed'})

        self.assertEqual(entry['result'], 'typed')
        self.assertIn(
            (GlueOperationKind.UPDATE, 'value'),
            [(operation.kind, operation.attribute) for operation in UpdateGuardedProbeGlue.operations],
        )

    def test_a_denied_draft_fails_before_any_draft_is_applied(self):
        with self.assertRaises(GlueAuthorizationError):
            self._call({'value': 'typed', 'other': 'denied'})

        self.assertEqual(self.glue_object.value, 'canonical')


class ProtocolAdmissionTestCase(TestCase):
    def setUp(self):
        self.glue_object = AdmissionProbeGlue()
        self.glue_object.request = request_with_session()
        self.policy = self.glue_object.policy

    def _admit(self, updates, policy=None):
        return self.glue_object._admit_updates(policy or self.policy, updates)

    def test_empty_updates_admit_to_nothing(self):
        self.assertEqual(self._admit({}), {})
        self.assertEqual(self._admit(None), {})

    def test_updates_must_be_a_json_object(self):
        with self.assertRaises(GlueRequestError) as context:
            self._admit(['value', 'other'])

        self.assertEqual(context.exception.code, GlueRequestErrorCode.INVALID_UPDATES)

    @override_settings(DJANGO_GLUE_MAX_UPDATES=1)
    def test_update_count_limit_is_enforced(self):
        with self.assertRaises(GlueRequestError) as context:
            self._admit({'value': 'a', 'other': 'b'})

        self.assertEqual(context.exception.code, GlueRequestErrorCode.INVALID_UPDATES)

    @override_settings(DJANGO_GLUE_MAX_UPDATES_ENCODED_BYTES=16)
    def test_update_encoded_size_limit_is_enforced(self):
        with self.assertRaises(GlueRequestError) as context:
            self._admit({'value': 'x' * 100})

        self.assertEqual(context.exception.code, GlueRequestErrorCode.INVALID_UPDATES)

    def test_unknown_attribute_is_rejected(self):
        with self.assertRaises(GlueRequestError) as context:
            self._admit({'missing': 'x'})

        self.assertEqual(context.exception.code, GlueRequestErrorCode.INVALID_UPDATES)
        self.assertEqual(context.exception.details()['attribute'], 'missing')

    def test_non_editable_attribute_is_rejected(self):
        with self.assertRaises(GlueRequestError) as context:
            self._admit({'derived': 'x'})

        self.assertEqual(context.exception.code, GlueRequestErrorCode.INVALID_UPDATES)
        self.assertEqual(context.exception.details()['attribute'], 'derived')

    def test_attribute_outside_the_signed_capability_is_rejected(self):
        data = self.policy.model_dump()
        data['attributes'] = [
            entry for entry in data['attributes'] if entry != 'value'
        ]
        narrowed = GluePolicy.new_signed_policy(data)

        with self.assertRaises(GlueRequestError) as context:
            self._admit({'value': 'x'}, policy=narrowed)

        self.assertEqual(context.exception.code, GlueRequestErrorCode.INVALID_UPDATES)
        self.assertEqual(context.exception.details()['attribute'], 'value')

    def test_valid_updates_pass_through(self):
        admitted = self._admit({'value': 'a', 'other': 'b'})

        self.assertEqual(admitted, {'value': 'a', 'other': 'b'})

    def test_annotated_update_is_coerced(self) -> None:
        admitted = self._admit({'number': '7'})

        assert admitted == {'number': 7}

    def test_malformed_annotated_update_is_rejected(self) -> None:
        with pytest.raises(GlueRequestError) as exception_info:
            self._admit({'number': 'not-a-number'})

        assert exception_info.value.code == GlueRequestErrorCode.INVALID_UPDATES
        assert exception_info.value.details()['attribute'] == 'number'

    def _call_echo(self, glue_object, policy, updates):
        context = AttributeCallRequestContext.model_construct(
            request=glue_object.request,
            target_glue_policy=policy,
            target_glue_updates=updates,
            target_attribute_name='echo',
            target_attribute_call_kwargs={},
        )
        entry, _introduced = glue_object.process_attribute_call(context)
        return entry

    def test_callable_sees_updates_merged_over_the_signed_snapshot(self):
        reconstructed = AdmissionProbeGlue._reconstruct_from_policy(self.policy)
        reconstructed.request = request_with_session()

        payload = self._call_echo(reconstructed, self.policy, {'value': 'draft'})

        self.assertEqual(payload['result'], 'draft')

    def test_admission_failure_runs_before_the_action_and_issues_no_token(self):
        reconstructed = AdmissionProbeGlue._reconstruct_from_policy(self.policy)
        reconstructed.request = request_with_session()

        with self.assertRaises(GlueRequestError) as context:
            self._call_echo(reconstructed, self.policy, {'derived': 'x'})

        self.assertEqual(context.exception.code, GlueRequestErrorCode.INVALID_UPDATES)


class ModelRelationLeafAdmissionTestCase(TestCase):
    def setUp(self):
        self.alpha = Gorilla.objects.create(name='Alpha', age=12)
        self.beta = Gorilla.objects.create(name='Beta', age=24)
        self.fight = Fight.objects.create(name='Bout', red_corner=self.alpha, blue_corner=self.beta)
        self.fight_two = Fight.objects.create(name='Rematch', red_corner=self.beta, blue_corner=self.alpha)

    def _glue(self, model, fields):
        glue_object = ModelGlue(model, name='target', access=GlueAccess.CHANGE, fields=fields)
        glue_object.request = request_with_session()
        return glue_object

    def test_nested_foreign_key_value_is_rejected(self):
        glue_object = self._glue(self.fight, ['name', 'red_corner'])

        with self.assertRaises(GlueRequestError) as context:
            glue_object._admit_updates(glue_object.policy, {'red_corner': {'pk': self.beta.pk}})

        self.assertEqual(context.exception.code, GlueRequestErrorCode.INVALID_UPDATES)
        self.assertEqual(context.exception.details()['attribute'], 'red_corner')

    def test_exposed_primary_key_is_never_client_editable(self):
        glue_object = self._glue(self.alpha, ['id', 'name'])

        self.assertNotIn('id', glue_object.editable)
        with self.assertRaises(GlueRequestError) as context:
            glue_object._admit_updates(glue_object.policy, {'id': self.beta.pk, 'name': 'Taken'})

        self.assertEqual(context.exception.code, GlueRequestErrorCode.INVALID_UPDATES)
        self.assertEqual(context.exception.details()['attribute'], 'id')
        with self.assertRaisesRegex(ValueError, 'primary key'):
            ModelGlue(self.alpha, name='target', access=GlueAccess.CHANGE, fields=['id'], editable=['id'])

    def test_flat_foreign_key_identity_is_admitted(self):
        glue_object = self._glue(self.fight, ['name', 'red_corner'])

        admitted = glue_object._admit_updates(
            glue_object.policy,
            {'red_corner': str(self.beta.pk)},
        )

        self.assertEqual(admitted, {'red_corner': self.beta.pk})

    def test_membership_list_of_objects_is_rejected(self):
        glue_object = self._glue(self.alpha, ['name', 'skills'])

        with self.assertRaises(GlueRequestError) as context:
            glue_object._admit_updates(glue_object.policy, {'skills': [{'pk': 1}]})

        self.assertEqual(context.exception.code, GlueRequestErrorCode.INVALID_UPDATES)

    def test_flat_membership_list_is_admitted(self):
        glue_object = self._glue(self.alpha, ['name', 'skills'])

        admitted = glue_object._admit_updates(glue_object.policy, {'skills': ['1', '2']})

        self.assertEqual(admitted, {'skills': [1, 2]})

    def test_file_field_is_not_updateable_as_a_value(self):
        glue_object = self._glue(self.alpha, ['name', 'profile_photo'])

        with self.assertRaises(GlueRequestError) as context:
            glue_object._admit_updates(
                glue_object.policy,
                {'profile_photo': {'name': 'x.png', 'url': '/media/x.png'}},
            )

        self.assertEqual(context.exception.code, GlueRequestErrorCode.INVALID_UPDATES)
        self.assertEqual(context.exception.details()['attribute'], 'profile_photo')

    def test_signed_scalar_snapshot_is_decoded_before_hydration(self) -> None:
        glue_object = self._glue(self.fight, ['date_time'])
        proposed = (self.fight.date_time + timedelta(days=1)).replace(
            microsecond=self.fight.date_time.microsecond // 1000 * 1000,
        )
        glue_object._load_client_state({'date_time': proposed})
        policy = GluePolicy.from_token(glue_object.policy.token)
        reconstructed = ModelGlue._reconstruct_from_policy(policy)
        reconstructed.request = request_with_session()
        context = AttributeCallRequestContext.model_construct(
            request=reconstructed.request,
            target_glue_policy=policy,
            target_glue_updates={},
            target_attribute_name=None,
            target_attribute_call_kwargs={},
        )

        reconstructed.process_attribute_call(context)

        assert isinstance(policy.state_snapshot['date_time'], str)
        assert reconstructed.instance.date_time == proposed


class FormChoiceLeafAdmissionTestCase(TestCase):
    def setUp(self):
        from django import forms

        class SkillChoiceForm(forms.Form):
            skill = forms.ModelChoiceField(queryset=Skill.objects.none(), required=False)

        class SkillMultiChoiceForm(forms.Form):
            skills = forms.ModelMultipleChoiceField(queryset=Skill.objects.none(), required=False)

        self.skill_choice_form = SkillChoiceForm
        self.skill_multi_choice_form = SkillMultiChoiceForm

    def _glue(self, form):
        glue_object = FormGlue(form, name='form', access=GlueAccess.CHANGE)
        glue_object.request = request_with_session()
        return glue_object

    def test_nested_choice_value_is_rejected(self):
        glue_object = self._glue(self.skill_choice_form())

        with self.assertRaises(GlueRequestError) as context:
            glue_object._admit_updates(glue_object.policy, {'skill': {'pk': 1}})

        self.assertEqual(context.exception.code, GlueRequestErrorCode.INVALID_UPDATES)
        self.assertEqual(context.exception.details()['attribute'], 'skill')

    def test_flat_choice_value_is_admitted(self):
        glue_object = self._glue(self.skill_choice_form())

        admitted = glue_object._admit_updates(glue_object.policy, {'skill': '1'})

        self.assertEqual(admitted, {'skill': '1'})

    def test_multi_choice_list_of_objects_is_rejected(self):
        glue_object = self._glue(self.skill_multi_choice_form())

        with self.assertRaises(GlueRequestError) as context:
            glue_object._admit_updates(glue_object.policy, {'skills': [{'pk': 1}]})

        self.assertEqual(context.exception.code, GlueRequestErrorCode.INVALID_UPDATES)

    def test_flat_multi_choice_list_is_admitted(self):
        glue_object = self._glue(self.skill_multi_choice_form())

        admitted = glue_object._admit_updates(glue_object.policy, {'skills': ['1', '2']})

        self.assertEqual(admitted, {'skills': ['1', '2']})


class RegisteredValue:
    def __init__(self, value: int) -> None:
        self.value = value


class RegisteredValueSerializer(GlueSerializerHandler):
    def supports(self, target: Any) -> bool:
        return target is RegisteredValue

    def coerce(self, value: Any, target: Any) -> RegisteredValue:
        _ = target
        return RegisteredValue(int(value))

    def decode(self, value: Any, target: Any) -> RegisteredValue:
        return self.coerce(value, target)


class SerializerRegistryTestCase(TestCase):
    def test_registered_handler_coerces_its_target_type(self) -> None:
        registry = GlueSerializerRegistry()
        registry.register(RegisteredValueSerializer())

        coerced = registry.coerce('7', RegisteredValue)

        assert isinstance(coerced, RegisteredValue)
        assert coerced.value == 7

    def test_missing_target_leaves_value_untouched(self) -> None:
        registry = GlueSerializerRegistry()

        assert registry.coerce('7', None) == '7'


class ModelStateSnapshotTestCase(TestCase):
    def setUp(self):
        self.gorilla = Gorilla.objects.create(name='Koko', age=18)
        self.glue_object = ModelGlue(
            self.gorilla,
            name='gorilla',
            access=GlueAccess.CHANGE,
            fields=['name', 'age'],
        )
        self.glue_object.request = request_with_session()

    def _save(self, glue_object, policy, updates):
        context = AttributeCallRequestContext.model_construct(
            request=glue_object.request,
            target_glue_policy=policy,
            target_glue_updates=updates,
            target_attribute_name='save',
            target_attribute_call_kwargs={},
        )
        payload, _introduced = glue_object.process_attribute_call(context)
        successor = (
            GluePolicy.from_token(payload['policy_token'])
            if 'policy_token' in payload
            else None
        )
        return payload, successor

    def test_fresh_object_signs_the_row_values_as_baseline(self):
        self.assertEqual(self.glue_object.policy.state_snapshot, {'name': 'Koko', 'age': 18})

    def test_acknowledged_draft_overrides_the_baseline_in_the_snapshot(self):
        self.glue_object._load_client_state({'name': 'Draft'})

        self.assertEqual(
            self.glue_object.policy.state_snapshot,
            {'name': 'Draft', 'age': 18, '$draft': ['name']},
        )

    def test_row_changed_out_of_band_supersedes_an_undrafted_baseline(self):
        self.glue_object._load_client_state({'name': 'Draft'})
        policy = self.glue_object.policy
        Gorilla.objects.filter(pk=self.gorilla.pk).update(name='Changed', age=40)
        reconstructed = ModelGlue._reconstruct_from_policy(policy)
        reconstructed.request = request_with_session()

        reconstructed._hydrate(policy, {})

        self.assertEqual(reconstructed._editable_draft, {'name': 'Draft'})
        self.assertEqual(reconstructed.instance.age, 40)
        self.assertEqual(reconstructed.policy.state_snapshot['age'], 40)

    def test_re_request_without_edits_keeps_the_draft_empty(self):
        policy = self.glue_object.policy
        reconstructed = ModelGlue._reconstruct_from_policy(policy)
        reconstructed.request = request_with_session()
        reconstructed._load_client_state(policy.state_snapshot)

        self.assertEqual(reconstructed._editable_draft, {})
        self.assertEqual(reconstructed.instance.name, 'Koko')
        self.assertEqual(reconstructed.instance.age, 18)

    def test_snapshot_values_matching_the_row_do_not_enter_the_draft(self):
        self.glue_object._load_client_state({'name': 'Draft'})
        policy = self.glue_object.policy
        reconstructed = ModelGlue._reconstruct_from_policy(policy)
        reconstructed.request = request_with_session()
        reconstructed._load_client_state(policy.state_snapshot)

        self.assertEqual(reconstructed._editable_draft, {'name': 'Draft'})

    def test_reconstruction_hydrates_snapshot_merged_with_updates(self):
        self.glue_object._load_client_state({'name': 'Draft'})
        policy = self.glue_object.policy

        reconstructed = ModelGlue._reconstruct_from_policy(policy)
        reconstructed.request = request_with_session()
        reconstructed._load_client_state({**policy.state_snapshot, 'age': 25})

        self.assertEqual(reconstructed.instance.name, 'Draft')
        self.assertEqual(reconstructed.instance.age, 25)

    def test_successful_save_rebases_the_successor_snapshot(self):
        fresh_policy = self.glue_object.policy
        self.glue_object._load_client_state({'name': 'Ndume', 'age': 22})
        payload, successor = self._save(
            self.glue_object,
            fresh_policy,
            {'name': 'Ndume', 'age': 22},
        )

        self.assertTrue(payload['result']['success'])
        self.assertEqual(successor.state_snapshot, {'name': 'Ndume', 'age': 22})

    def test_failed_save_retains_the_coerced_draft_in_the_successor_snapshot(self) -> None:
        fresh_policy = self.glue_object.policy
        payload, successor = self._save(
            self.glue_object,
            fresh_policy,
            {'age': '0'},
        )

        self.assertFalse(payload['result']['success'])
        self.assertEqual(successor.state_snapshot, {'name': 'Koko', 'age': 0, '$draft': ['age']})
        self.gorilla.refresh_from_db()
        self.assertEqual(self.gorilla.age, 18)

    def test_malformed_model_update_is_rejected_before_save(self) -> None:
        with pytest.raises(GlueRequestError) as exception_info:
            self._save(
                self.glue_object,
                self.glue_object.policy,
                {'age': 'not-a-number'},
            )

        assert exception_info.value.code == GlueRequestErrorCode.INVALID_UPDATES
        self.gorilla.refresh_from_db()
        assert self.gorilla.age == 18

    def test_model_callable_sees_coerced_update_on_the_instance(self) -> None:
        context = AttributeCallRequestContext.model_construct(
            request=self.glue_object.request,
            target_glue_policy=self.glue_object.policy,
            target_glue_updates={'age': '25'},
            target_attribute_name='something',
            target_attribute_call_kwargs={},
        )

        self.glue_object.process_attribute_call(context)

        self.gorilla.refresh_from_db()
        assert self.gorilla.age == 26

    def test_saving_one_field_keeps_a_concurrent_change_to_another(self):
        policy = self.glue_object.policy
        Gorilla.objects.filter(pk=self.gorilla.pk).update(age=30)
        reconstructed = ModelGlue._reconstruct_from_policy(policy)
        reconstructed.request = request_with_session()

        payload, _successor = self._save(reconstructed, policy, {'name': 'Renamed'})

        self.assertTrue(payload['result']['success'])
        self.gorilla.refresh_from_db()
        self.assertEqual((self.gorilla.name, self.gorilla.age), ('Renamed', 30))

    def test_save_changing_nothing_omits_the_successor_token(self):
        payload, successor = self._save(self.glue_object, self.glue_object.policy, {})

        self.assertTrue(payload['result']['success'])
        self.assertNotIn('policy_token', payload)
        self.assertIsNone(successor)

    def test_saving_a_signed_draft_re_signs_it_as_the_baseline(self):
        self.glue_object._load_client_state({'name': 'Ndume', 'age': 22})
        payload, successor = self._save(
            self.glue_object,
            self.glue_object.policy,
            {'name': 'Ndume', 'age': 22},
        )

        self.assertTrue(payload['result']['success'])
        self.assertEqual(successor.state_snapshot, {'name': 'Ndume', 'age': 22})
        self.gorilla.refresh_from_db()
        self.assertEqual(self.gorilla.age, 22)
