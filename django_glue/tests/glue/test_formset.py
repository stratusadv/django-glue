from __future__ import annotations


from django import forms
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from django_glue import Glue
from django_glue.access import GlueAccess
from django_glue.exceptions import (
    GlueAccessError,
    GlueFormSetMaxNumExceededError,
    GlueRequestError,
)
from django_glue.glue.objects.django.form.object import FormGlue
from django_glue.glue.objects.django.formset import FormSetGlue
from django_glue.glue.policy import GluePolicy
from django_glue.glue.registry import glue_class_registry
from django_glue.resolver.attribute_call.context import AttributeCallRequestContext
from test_project.fight.models import Fight
from test_project.gorilla.forms import FightNameForm, GorillaForm
from test_project.gorilla.models import Gorilla, Skill
from test_project.test_forms import ContactForm, TestModelForm

from django_glue.tests.glue.test_objects import (
    glue_context,
    request_with_session,
    with_request,
)


class SampleContactFormSet(Glue.FormSet):
    """Module-level so ``get_attr_from_path_string`` can resolve it on reconstruction."""

    form_class = ContactForm
    min_num = 1
    max_num = 5

    def clean(self, form_list):
        return ['Test cross-form error.']


class SubmittingContactFormSet(Glue.FormSet):
    form_class = ContactForm
    min_num = 1
    can_delete = True

    @Glue.attr(required_access=Glue.Access.CHANGE)
    def submit(self):
        validation = self.validate()
        return {
            'valid': validation['valid'],
            'names': [form.bound_form.cleaned_data['name'] for form in validation['form_list']]
            if validation['valid'] else [],
        }


class SoftDeletingGorillaFormSet(Glue.FormSet):
    form_class = TestModelForm
    can_delete = True

    def delete_removed(self, queryset):
        queryset.update(description='retired')


class HookSavingGorillaFormSet(Glue.FormSet):
    form_class = TestModelForm

    def save_forms(self, form_list):
        for form in form_list:
            gorilla = form.save(commit=False)
            gorilla.description = 'saved by hook'
            gorilla.save()


def call_across_requests(policy, attribute, kwargs):
    """
    Run one attribute call the way a later request would: rebuilt from the token alone.
    """
    reconstructed = FormSetGlue._reconstruct_from_policy(policy)
    reconstructed.request = request_with_session()
    context = AttributeCallRequestContext.model_construct(
        request=reconstructed.request,
        target_glue_policy=policy,
        target_glue_updates={},
        target_attribute_name=attribute,
        target_attribute_call_kwargs=kwargs,
        reintroduce=[],
    )
    return reconstructed.process_attribute_call(context)


def row_tokens(glue_object):
    """
    The signed form token of each row, by row key.
    """
    tokens_by_address = {
        entry['address']: entry['policy_token']
        for entry in glue_object._serialized_child_entries()
    }
    return {key: tokens_by_address[address] for key, address in glue_object.policy.children.items()}


class FormSetGlueRemovalTestCase(TestCase):
    def setUp(self):
        self.koko = Gorilla.objects.create(name='Koko')
        self.harambe = Gorilla.objects.create(name='Harambe')

    def seeded_formset(self, access=GlueAccess.DELETE, formset_class=FormSetGlue, **kwargs):
        return with_request(formset_class(
            TestModelForm,
            instances=[self.koko, self.harambe],
            can_delete=True,
            **glue_context(name='gorillas', access=access),
            **kwargs,
        ))

    def pop_row(self, policy, key, token):
        entry, _ = call_across_requests(policy, 'pop', {
            'key': key,
            '__submitted_forms': {key: {'policy_token': token}},
        })
        return GluePolicy.from_token(entry['policy_token'])

    def test_pop_of_a_saved_row_signs_its_pk_for_deletion_without_deleting(self):
        formset = self.seeded_formset()
        tokens = row_tokens(formset)

        successor = self.pop_row(formset.policy, '0', tokens['0'])

        self.assertEqual(successor.state_snapshot['removed_pks'], [self.koko.pk])
        self.assertEqual(list(successor.children), ['1'])
        self.assertTrue(Gorilla.objects.filter(pk=self.koko.pk).exists())

    def test_pop_of_an_unsaved_row_signs_nothing_for_deletion(self):
        formset = self.seeded_formset(initial=[{'name': 'New'}])
        tokens = row_tokens(formset)

        successor = self.pop_row(formset.policy, '2', tokens['2'])

        self.assertNotIn('removed_pks', successor.state_snapshot)

    def test_save_deletes_removed_rows_and_clears_the_pending_list(self):
        formset = self.seeded_formset()
        tokens = row_tokens(formset)
        policy = self.pop_row(formset.policy, '0', tokens['0'])

        entry, _ = call_across_requests(policy, 'save', {
            '__submitted_forms': {'1': {'policy_token': tokens['1'], 'updates': {'name': 'Harambe II'}}},
        })

        self.assertEqual(entry['result'], {'valid': True})
        self.assertEqual(
            list(Gorilla.objects.values_list('name', flat=True)),
            ['Harambe II'],
        )
        self.assertNotIn('removed_pks', GluePolicy.from_token(entry['policy_token']).state_snapshot)

    def test_save_with_an_invalid_row_saves_and_deletes_nothing(self):
        formset = self.seeded_formset(initial=[{'name': 'New'}])
        tokens = row_tokens(formset)
        policy = self.pop_row(formset.policy, '0', tokens['0'])

        entry, _ = call_across_requests(policy, 'save', {'__submitted_forms': {
            '1': {'policy_token': tokens['1'], 'updates': {'name': 'Harambe II'}},
            '2': {'policy_token': tokens['2'], 'updates': {'name': ''}},
        }})

        self.assertEqual(entry['result'], {'valid': False})
        self.assertEqual(
            list(Gorilla.objects.order_by('pk').values_list('name', flat=True)),
            ['Koko', 'Harambe'],
        )

    def test_save_query_count_does_not_grow_with_removed_rows(self):
        query_counts = []

        for removed_count in (1, 3):
            removed = [Gorilla.objects.create(name=f'Removed {index}') for index in range(removed_count)]
            formset = with_request(FormSetGlue(
                TestModelForm,
                instances=[*removed, self.harambe],
                can_delete=True,
                **glue_context(name='gorillas', access=GlueAccess.DELETE),
            ))
            tokens = row_tokens(formset)
            policy = formset.policy
            for key in map(str, range(removed_count)):
                policy = self.pop_row(policy, key, tokens[key])
            kept_key = str(removed_count)

            with CaptureQueriesContext(connection) as queries:
                call_across_requests(policy, 'save', {
                    '__submitted_forms': {kept_key: {'policy_token': tokens[kept_key], 'updates': {}}},
                })

            query_counts.append(len(queries))

        self.assertEqual(query_counts[0], query_counts[1])
        self.assertEqual(Gorilla.objects.filter(name__startswith='Removed').count(), 0)

    def test_pop_of_a_saved_row_requires_delete_access(self):
        formset = self.seeded_formset(access=GlueAccess.CHANGE)
        tokens = row_tokens(formset)

        with self.assertRaises(GlueAccessError):
            self.pop_row(formset.policy, '0', tokens['0'])

    def test_pop_of_an_unsaved_row_needs_only_change_access(self):
        formset = self.seeded_formset(access=GlueAccess.CHANGE, initial=[{'name': 'New'}])
        tokens = row_tokens(formset)

        successor = self.pop_row(formset.policy, '2', tokens['2'])

        self.assertEqual(list(successor.children), ['0', '1'])

    def test_pop_of_a_live_row_requires_its_signed_token(self):
        formset = self.seeded_formset()

        with self.assertRaisesRegex(GlueRequestError, 'match signed membership'):
            call_across_requests(formset.policy, 'pop', {'key': '0'})

    def test_pop_rejects_the_token_of_another_row(self):
        formset = self.seeded_formset()
        tokens = row_tokens(formset)

        with self.assertRaisesRegex(GlueRequestError, 'does not belong'):
            self.pop_row(formset.policy, '0', tokens['1'])

    def test_pop_rejects_a_row_signed_for_a_same_named_formset_with_less_access(self):
        change_only = with_request(FormSetGlue(
            TestModelForm,
            instances=[self.koko],
            can_delete=True,
            **glue_context(name='gorillas', access=GlueAccess.CHANGE),
        ))
        deletable = with_request(FormSetGlue(
            TestModelForm,
            instances=[self.harambe],
            can_delete=True,
            **glue_context(name='gorillas', access=GlueAccess.DELETE),
        ))

        with self.assertRaisesRegex(GlueRequestError, 'does not belong'):
            self.pop_row(deletable.policy, '0', row_tokens(change_only)['0'])

    def test_pop_rejects_a_row_signed_for_a_same_named_formset_with_the_same_access(self):
        other = with_request(FormSetGlue(
            TestModelForm,
            instances=[self.harambe, self.koko],
            can_delete=True,
            **glue_context(name='gorillas', access=GlueAccess.DELETE),
        ))
        formset = self.seeded_formset()

        with self.assertRaisesRegex(GlueRequestError, 'does not belong'):
            self.pop_row(formset.policy, '0', row_tokens(other)['0'])

    def test_save_rejects_a_new_row_signed_for_a_view_only_formset(self):
        view_only = with_request(FormSetGlue(
            TestModelForm,
            initial=[{'name': 'Sneaky'}],
            **glue_context(name='gorillas', access=GlueAccess.VIEW),
        ))
        formset = with_request(FormSetGlue(
            TestModelForm,
            initial=[{'name': 'Real'}],
            **glue_context(name='gorillas', access=GlueAccess.CHANGE),
        ))

        with self.assertRaisesRegex(GlueRequestError, 'does not belong'):
            call_across_requests(formset.policy, 'save', {
                '__submitted_forms': {'0': {'policy_token': row_tokens(view_only)['0']}},
            })

        self.assertFalse(Gorilla.objects.filter(name='Sneaky').exists())

    def test_rows_reissued_by_save_are_accepted_by_the_next_save(self):
        formset = self.seeded_formset()
        tokens = row_tokens(formset)
        submitted = {
            '0': {'policy_token': tokens['0'], 'updates': {'name': 'Koko II'}},
            '1': {'policy_token': tokens['1']},
        }
        entry, introduced = call_across_requests(formset.policy, 'save', {'__submitted_forms': submitted})
        policy = GluePolicy.from_token(entry['policy_token']) if 'policy_token' in entry else formset.policy
        reissued = {row['address']: row['policy_token'] for row in introduced}

        entry, _ = call_across_requests(policy, 'save', {
            '__submitted_forms': {
                key: {'policy_token': reissued[address]} for key, address in policy.children.items()
            },
        })

        self.assertEqual(entry['result'], {'valid': True})

    def test_a_formset_token_issued_before_rows_were_bound_still_accepts_its_rows(self):
        formset = self.seeded_formset()
        tokens = row_tokens(formset)
        legacy_state = {
            key: value for key, value in formset.policy.state_snapshot.items() if key != 'row_bindings'
        }
        legacy = formset.policy.model_copy(update={'state_snapshot': legacy_state})

        successor = self.pop_row(legacy, '0', tokens['0'])

        self.assertEqual(successor.state_snapshot['removed_pks'], [self.koko.pk])
        self.assertNotIn('row_bindings', successor.state_snapshot)

    def test_delete_removed_hook_replaces_the_hard_delete(self):
        formset = with_request(SoftDeletingGorillaFormSet(
            instances=[self.koko, self.harambe],
            **glue_context(name='gorillas', access=GlueAccess.DELETE),
        ))
        tokens = row_tokens(formset)
        policy = self.pop_row(formset.policy, '0', tokens['0'])

        call_across_requests(policy, 'save', {
            '__submitted_forms': {'1': {'policy_token': tokens['1'], 'updates': {}}},
        })

        self.koko.refresh_from_db()
        self.assertEqual(self.koko.description, 'retired')

    def test_save_forms_hook_replaces_the_per_form_save(self):
        formset = with_request(HookSavingGorillaFormSet(
            instances=[self.koko],
            **glue_context(name='gorillas'),
        ))
        tokens = row_tokens(formset)

        entry, _ = call_across_requests(formset.policy, 'save', {
            '__submitted_forms': {'0': {'policy_token': tokens['0'], 'updates': {'name': 'Koko II'}}},
        })

        self.assertEqual(entry['result'], {'valid': True})
        self.koko.refresh_from_db()
        self.assertEqual((self.koko.name, self.koko.description), ('Koko II', 'saved by hook'))


class DisabledNameGorillaForm(forms.ModelForm):
    name = forms.CharField(disabled=True)

    class Meta:
        model = Gorilla
        fields = ['name', 'age']


class FormSetGlueNewRowTestCase(TestCase):
    def setUp(self):
        self.koko = Gorilla.objects.create(name='Koko')
        self.rival = Gorilla.objects.create(name='Rival')

    def append_and_save(self, formset, initial):
        entry, introduced = call_across_requests(formset.policy, 'append', {'key': 'new', 'initial': initial})
        return call_across_requests(GluePolicy.from_token(entry['policy_token']), 'save', {
            '__submitted_forms': {'new': {'policy_token': introduced[0]['policy_token'], 'updates': {}}},
        })

    def test_a_new_row_is_accepted_after_a_call_of_its_own(self):
        formset = with_request(FormSetGlue(
            TestModelForm,
            can_delete=True,
            **glue_context(name='gorillas', access=GlueAccess.DELETE),
        ))
        entry, introduced = call_across_requests(formset.policy, 'append', {
            'key': 'new',
            'initial': {'name': 'Koko II'},
        })
        row_policy = GluePolicy.from_token(introduced[0]['policy_token'])

        row_context = AttributeCallRequestContext.model_construct(
            request=request_with_session(),
            target_glue_policy=row_policy,
            target_glue_updates={},
            target_attribute_name='validate',
            target_attribute_call_kwargs={},
            reintroduce=[],
        )
        row = FormGlue.from_attribute_call_resolver_context(row_context)
        row_entry, _ = row.process_attribute_call(row_context)
        # The client holds the renewed token when the call sent one.
        row_token = row_entry.get('policy_token', introduced[0]['policy_token'])

        popped, _ = call_across_requests(GluePolicy.from_token(entry['policy_token']), 'pop', {
            'key': 'new',
            '__submitted_forms': {'new': {'policy_token': row_token}},
        })

        self.assertEqual(list(GluePolicy.from_token(popped['policy_token']).children), [])

    def test_append_rejects_initial_for_a_field_the_form_does_not_expose(self):
        formset = with_request(FormSetGlue(FightNameForm, **glue_context(name='fights')))

        with self.assertRaisesRegex(GlueRequestError, 'editable form fields') as caught:
            call_across_requests(formset.policy, 'append', {'key': 'new', 'initial': {
                'name': 'Sneaky',
                'red_corner': self.koko.pk,
                'spectator_count': 999999,
            }})

        self.assertEqual(caught.exception.details(), {'fields': ['red_corner', 'spectator_count']})

    def test_new_row_defaults_set_unexposed_fields_on_an_appended_row(self):
        formset = with_request(FormSetGlue(
            FightNameForm,
            new_row_defaults={'red_corner': self.koko.pk, 'blue_corner': self.rival.pk},
            **glue_context(name='fights'),
        ))

        entry, _ = self.append_and_save(formset, {'name': 'Title Bout'})

        self.assertEqual(entry['result'], {'valid': True})
        fight = Fight.objects.get(name='Title Bout')
        self.assertEqual((fight.red_corner, fight.blue_corner), (self.koko, self.rival))

    def test_new_row_defaults_win_over_the_clients_initial(self):
        formset = with_request(FormSetGlue(
            TestModelForm,
            new_row_defaults={'name': 'Fixed'},
            **glue_context(name='gorillas'),
        ))

        self.append_and_save(formset, {'name': 'Chosen by the client'})

        self.assertTrue(Gorilla.objects.filter(name='Fixed').exists())
        self.assertFalse(Gorilla.objects.filter(name='Chosen by the client').exists())

    def test_a_default_on_an_editable_field_is_a_starting_value_the_user_may_change(self):
        formset = with_request(FormSetGlue(
            TestModelForm,
            new_row_defaults={'name': 'Suggested'},
            **glue_context(name='gorillas'),
        ))
        entry, introduced = call_across_requests(formset.policy, 'append', {'key': 'new'})

        call_across_requests(GluePolicy.from_token(entry['policy_token']), 'save', {
            '__submitted_forms': {'new': {
                'policy_token': introduced[0]['policy_token'],
                'updates': {'name': 'Typed by the user'},
            }},
        })

        self.assertTrue(Gorilla.objects.filter(name='Typed by the user').exists())
        self.assertFalse(Gorilla.objects.filter(name='Suggested').exists())

    def test_a_default_on_a_disabled_field_cannot_be_changed_by_the_client(self):
        formset = with_request(FormSetGlue(
            DisabledNameGorillaForm,
            new_row_defaults={'name': 'Fixed'},
            **glue_context(name='gorillas'),
        ))
        entry, introduced = call_across_requests(formset.policy, 'append', {'key': 'new'})
        policy = GluePolicy.from_token(entry['policy_token'])
        token = introduced[0]['policy_token']

        with self.assertRaises(GlueRequestError):
            call_across_requests(policy, 'save', {
                '__submitted_forms': {'new': {'policy_token': token, 'updates': {'name': 'Client'}}},
            })
        self.assertFalse(Gorilla.objects.filter(name='Client').exists())

        call_across_requests(policy, 'save', {
            '__submitted_forms': {'new': {'policy_token': token, 'updates': {'age': 7}}},
        })
        self.assertEqual(Gorilla.objects.get(name='Fixed').age, 7)

    def test_new_row_defaults_apply_to_seeded_initial_rows(self):
        formset = with_request(FormSetGlue(
            FightNameForm,
            initial=[{'name': 'Seeded Bout'}],
            new_row_defaults={'red_corner': self.koko.pk, 'blue_corner': self.rival.pk},
            **glue_context(name='fights'),
        ))
        policy = formset.policy
        tokens = row_tokens(formset)

        call_across_requests(policy, 'save', {
            '__submitted_forms': {'0': {'policy_token': tokens['0'], 'updates': {}}},
        })

        self.assertEqual(Fight.objects.get(name='Seeded Bout').red_corner, self.koko)

    def test_new_row_defaults_apply_to_an_unsaved_form_passed_through_instances(self):
        formset = with_request(FormSetGlue(
            FightNameForm,
            instances=[FightNameForm(initial={'name': 'Prepared Bout', 'red_corner': self.rival.pk})],
            new_row_defaults={'red_corner': self.koko.pk, 'blue_corner': self.rival.pk},
            **glue_context(name='fights'),
        ))
        policy = formset.policy
        tokens = row_tokens(formset)

        entry, _ = call_across_requests(policy, 'save', {
            '__submitted_forms': {'0': {'policy_token': tokens['0'], 'updates': {}}},
        })

        self.assertEqual(entry['result'], {'valid': True})
        fight = Fight.objects.get(name='Prepared Bout')
        self.assertEqual((fight.red_corner, fight.blue_corner), (self.koko, self.rival))

    def test_new_row_defaults_leave_a_form_for_a_saved_record_alone(self):
        fight = Fight.objects.create(name='Old Bout', red_corner=self.rival, blue_corner=self.rival)
        formset = with_request(FormSetGlue(
            FightNameForm,
            instances=[FightNameForm(instance=fight)],
            new_row_defaults={'red_corner': self.koko.pk, 'name': 'Default'},
            **glue_context(name='fights'),
        ))
        policy = formset.policy
        tokens = row_tokens(formset)

        call_across_requests(policy, 'save', {
            '__submitted_forms': {'0': {'policy_token': tokens['0'], 'updates': {'name': 'Old Bout II'}}},
        })

        fight.refresh_from_db()
        self.assertEqual((fight.name, fight.red_corner), ('Old Bout II', self.rival))

    def test_shortcut_passes_new_row_defaults(self):
        glue_object = Glue.formset(
            target=FightNameForm,
            unique_name='fights',
            new_row_defaults={'red_corner': self.koko.pk},
        )

        self.assertEqual(glue_object.get_identity()['new_row_defaults'], {'red_corner': self.koko.pk})


class FightCornersForm(forms.ModelForm):
    class Meta:
        model = Fight
        fields = ['name', 'red_corner', 'blue_corner']


class FormSetGlueQueryCountTestCase(TestCase):
    def queries_for(self, form_class, row_count, attribute, updates_by_key=None):
        Gorilla.objects.all().delete()
        gorillas = [Gorilla.objects.create(name=f'Gorilla {index}') for index in range(row_count)]
        formset = with_request(FormSetGlue(
            form_class,
            instances=gorillas,
            **glue_context(name='gorillas'),
        ))
        policy = formset.policy
        submitted = {
            key: {'policy_token': token, 'updates': (updates_by_key or {}).get(key, {})}
            for key, token in row_tokens(formset).items()
        }

        with CaptureQueriesContext(connection) as queries:
            entry, _ = call_across_requests(policy, attribute, {'__submitted_forms': submitted})

        self.assertTrue(entry['result']['valid'])
        return [query['sql'] for query in queries]

    def test_submitted_rows_are_loaded_in_a_constant_number_of_queries(self):
        for form_class, expected_selects in ((TestModelForm, 1), (GorillaForm, 2)):
            with self.subTest(form_class=form_class.__name__):
                for row_count in (2, 6):
                    queries = self.queries_for(form_class, row_count, 'validate')

                    self.assertEqual(len(queries), expected_selects)

    def test_save_writes_only_the_saved_rows_that_changed(self):
        queries = self.queries_for(TestModelForm, 4, 'save', {'2': {'name': 'Renamed'}})

        self.assertEqual(len([sql for sql in queries if sql.startswith('UPDATE')]), 1)
        self.assertEqual(Gorilla.objects.filter(name='Renamed').count(), 1)

    def test_each_foreign_key_field_costs_djangos_two_validation_queries_per_row(self):
        koko = Gorilla.objects.create(name='Koko')
        harambe = Gorilla.objects.create(name='Harambe')

        for row_count in (2, 6):
            with self.subTest(row_count=row_count):
                Fight.objects.all().delete()
                formset = with_request(FormSetGlue(
                    FightCornersForm,
                    instances=[
                        Fight.objects.create(name=f'Fight {index}', red_corner=koko, blue_corner=harambe)
                        for index in range(row_count)
                    ],
                    **glue_context(name='fights'),
                ))
                policy = formset.policy
                submitted = {
                    key: {'policy_token': token, 'updates': {}}
                    for key, token in row_tokens(formset).items()
                }

                with CaptureQueriesContext(connection) as queries:
                    call_across_requests(policy, 'validate', {'__submitted_forms': submitted})

                row_loads = [query for query in queries if 'FROM "fight"' in query['sql']]
                related_lookups = [query for query in queries if 'FROM "gorilla"' in query['sql']]
                self.assertEqual(len(row_loads), 1)
                # ModelChoiceField fetches the related record and
                # ForeignKey.validate checks it exists, for each of two fields.
                self.assertEqual(len(related_lookups), row_count * 2 * 2)
                self.assertEqual(len(queries), len(row_loads) + len(related_lookups))

    def test_save_creates_a_new_row_the_user_did_not_edit(self):
        formset = with_request(FormSetGlue(
            TestModelForm,
            initial=[{'name': 'Prefilled'}],
            **glue_context(name='gorillas'),
        ))
        policy = formset.policy
        tokens = row_tokens(formset)

        call_across_requests(policy, 'save', {
            '__submitted_forms': {'0': {'policy_token': tokens['0'], 'updates': {}}},
        })

        self.assertEqual(Gorilla.objects.filter(name='Prefilled').count(), 1)


class FormSetGlueTestCase(TestCase):
    def test_attributes_expose_declared_attributes_and_keyed_forms(self):
        glue_object = with_request(FormSetGlue(ContactForm, **glue_context(name='contacts')))
        glue_object.append(key='1', initial={})

        self.assertIn('append', glue_object.attributes)
        self.assertIn('validate', glue_object.attributes)
        # Keyed children are addressed by their key, not a positional attribute.
        self.assertIn('1', glue_object.children)

    def test_identity_captures_formset_configuration(self):
        glue_object = FormSetGlue(
            ContactForm,
            **glue_context(name='contacts'),
            min_num=1,
            max_num=5,
            can_delete=True,
        )

        identity = glue_object.get_identity()

        self.assertEqual(identity['form_class_path'], 'test_project.test_forms.ContactForm')
        self.assertEqual(identity['min_num'], 1)
        self.assertEqual(identity['max_num'], 5)
        self.assertTrue(identity['can_delete'])

    def test_requires_a_form_class(self):
        with self.assertRaises(ValueError):
            FormSetGlue(**glue_context(name='contacts'))

    def test_shortcut_rejects_a_django_formset_instance_naming_the_fix(self):
        formset = forms.formset_factory(ContactForm)()

        with self.assertRaisesRegex(TypeError, 'Glue.FormSet subclass'):
            Glue.formset(None, 'contacts', formset)

    def test_validated_forms_expose_their_bound_django_form(self):
        glue_object = with_request(FormSetGlue(ContactForm, **glue_context(name='contacts')))
        glue_object.append(key='1', initial={})
        glue_object._load_client_state({'forms': {'1': {
            'name': 'Ada', 'email': 'ada@example.com', 'message': 'Hello', 'priority': 'low',
        }}})

        result = glue_object.validate()

        bound_form = result['form_list'][0].bound_form
        self.assertIsInstance(bound_form, ContactForm)
        self.assertTrue(bound_form.is_bound)
        self.assertEqual(bound_form.cleaned_data['name'], 'Ada')

    def test_append_returns_a_bound_form_glue_with_initial_values(self):
        glue_object = with_request(FormSetGlue(ContactForm, **glue_context(name='contacts')))

        appended = glue_object.append(key='1', initial={'name': 'Ada'})

        self.assertEqual(appended.state['name']['value'], 'Ada')
        self.assertEqual(glue_object.get_keyed_items(), [('1', appended)])

    def test_append_rejects_when_max_num_is_reached(self):
        glue_object = with_request(FormSetGlue(
            ContactForm, **glue_context(name='contacts'), max_num=2,
        ))
        glue_object.append(key='1', initial={})
        glue_object.append(key='2', initial={})

        with self.assertRaises(GlueFormSetMaxNumExceededError) as caught:
            glue_object.append(key='3', initial={})

        self.assertEqual(caught.exception.current_count, 2)
        self.assertEqual(caught.exception.max_num, 2)
        self.assertEqual(len(glue_object.get_keyed_items()), 2)

    def test_append_is_unbounded_when_max_num_is_none(self):
        glue_object = with_request(FormSetGlue(ContactForm, **glue_context(name='contacts')))

        for key in ('1', '2', '3'):
            glue_object.append(key=key, initial={})

        self.assertEqual(len(glue_object.get_keyed_items()), 3)

    def test_append_attribute_call_introduces_the_new_child_as_an_entry(self):
        glue_object = with_request(FormSetGlue(ContactForm, **glue_context(name='contacts')))
        policy = glue_object.policy
        reconstructed = FormSetGlue._reconstruct_from_policy(policy)
        reconstructed.request = request_with_session()
        context = AttributeCallRequestContext.model_construct(
            request=reconstructed.request,
            target_glue_policy=policy,
            target_glue_updates={},
            target_attribute_name='append',
            target_attribute_call_kwargs={'key': '1', 'initial': {'name': 'Ada'}},
        )

        entry, introduced = reconstructed.process_attribute_call(context)

        self.assertEqual(len(introduced), 1)
        introduction = introduced[0]
        child_policy = GluePolicy.from_token(introduction['policy_token'])
        self.assertEqual(child_policy.name, 'contacts.1')
        self.assertEqual(child_policy.namespace, 'form')
        self.assertEqual(child_policy.state_snapshot['name'], 'Ada')
        self.assertEqual(introduction['address'], entry['result'])
        successor = GluePolicy.from_token(entry['policy_token'])
        self.assertEqual(successor.children, {'1': introduction['address']})

    def test_rows_survive_separate_append_requests(self):
        original = with_request(FormSetGlue(
            ContactForm, **glue_context(name='contacts'), max_num=2,
        ))
        policy = original.policy

        for key in ('first', 'second'):
            reconstructed = FormSetGlue._reconstruct_from_policy(policy)
            reconstructed.request = request_with_session()
            context = AttributeCallRequestContext.model_construct(
                request=reconstructed.request,
                target_glue_policy=policy,
                target_glue_updates={},
                target_attribute_name='append',
                target_attribute_call_kwargs={'key': key, 'initial': {}},
                reintroduce=[],
            )
            entry, introduced = reconstructed.process_attribute_call(context)
            self.assertEqual(len(introduced), 1)
            policy = GluePolicy.from_token(entry['policy_token'])

        self.assertEqual(list(policy.children), ['first', 'second'])

    def test_remove_and_submit_uses_surviving_row_values_across_requests(self):
        original = with_request(SubmittingContactFormSet(name='contacts'))
        policy = original.policy
        child_policies = {}

        for key in ('first', 'second'):
            entry, introduced = call_across_requests(policy, 'append', {'key': key, 'initial': {}})
            self.assertNotIn('error', entry)
            for child in introduced:
                child_policy = GluePolicy.from_token(child['policy_token'])
                child_policies[child_policy.name.rsplit('.', 1)[-1]] = child_policy
            policy = GluePolicy.from_token(entry['policy_token'])

        entry, _ = call_across_requests(policy, 'pop', {
            'key': 'first',
            '__submitted_forms': {'first': {'policy_token': child_policies['first'].token}},
        })
        policy = GluePolicy.from_token(entry['policy_token'])

        self.assertEqual(list(policy.children), ['second'])

        reconstructed = FormSetGlue._reconstruct_from_policy(policy)
        reconstructed.request = request_with_session()
        context = AttributeCallRequestContext.model_construct(
            request=reconstructed.request,
            target_glue_policy=policy,
            target_glue_updates={},
            target_attribute_name='submit',
            target_attribute_call_kwargs={'__submitted_forms': {
                'second': {
                    'policy_token': child_policies['second'].token,
                    'updates': {
                        'name': 'Bee',
                        'email': 'bee@example.com',
                        'message': 'Surviving row',
                        'priority': 'low',
                    },
                },
            }},
            reintroduce=[],
        )

        entry, _ = reconstructed.process_attribute_call(context)

        self.assertEqual(entry['result'], {'valid': True, 'names': ['Bee']})

    def test_submit_rejects_a_form_token_outside_signed_membership(self):
        original = with_request(FormSetGlue(ContactForm, **glue_context(name='contacts')))
        original.append(key='first', initial={})
        policy = original.policy
        foreign = with_request(FormSetGlue(ContactForm, **glue_context(name='other')))
        foreign_policy = foreign.policy
        foreign_reconstructed = FormSetGlue._reconstruct_from_policy(foreign_policy)
        foreign_reconstructed.request = request_with_session()
        foreign_context = AttributeCallRequestContext.model_construct(
            request=foreign_reconstructed.request,
            target_glue_policy=foreign_policy,
            target_glue_updates={},
            target_attribute_name='append',
            target_attribute_call_kwargs={'key': 'first', 'initial': {}},
            reintroduce=[],
        )
        _, foreign_children = foreign_reconstructed.process_attribute_call(foreign_context)
        foreign_token = foreign_children[0]['policy_token']

        reconstructed = FormSetGlue._reconstruct_from_policy(policy)
        reconstructed.request = request_with_session()
        context = AttributeCallRequestContext.model_construct(
            request=reconstructed.request,
            target_glue_policy=policy,
            target_glue_updates={},
            target_attribute_name='validate',
            target_attribute_call_kwargs={'__submitted_forms': {
                'first': {'policy_token': foreign_token, 'updates': {}},
            }},
            reintroduce=[],
        )

        with self.assertRaisesRegex(GlueRequestError, 'does not belong'):
            reconstructed.process_attribute_call(context)

    def test_attribute_call_without_child_changes_omits_introductions(self):
        glue_object = with_request(FormSetGlue(ContactForm, **glue_context(name='contacts')))
        policy = glue_object.policy
        reconstructed = FormSetGlue._reconstruct_from_policy(policy)
        reconstructed.request = request_with_session()
        context = AttributeCallRequestContext.model_construct(
            request=reconstructed.request,
            target_glue_policy=policy,
            target_glue_updates={},
            target_attribute_name='validate',
            target_attribute_call_kwargs={},
        )

        entry, introduced = reconstructed.process_attribute_call(context)

        self.assertEqual(introduced, [])
        self.assertNotIn('policy_token', entry)
        self.assertTrue(entry['result']['valid'])

    def test_validate_attribute_call_returns_row_addresses_not_forms(self):
        formset = with_request(FormSetGlue(
            ContactForm,
            initial=[{'name': 'Ada', 'email': 'ada@example.com', 'message': 'Hello', 'priority': 'low'}],
            **glue_context(name='contacts'),
        ))
        policy = formset.policy
        tokens = row_tokens(formset)

        entry, _ = call_across_requests(policy, 'validate', {
            '__submitted_forms': {'0': {'policy_token': tokens['0'], 'updates': {}}},
        })

        self.assertEqual(entry['result'], {
            'valid': True,
            'form_list': [policy.children['0']],
            'non_form_errors': [],
        })

    def test_collection_starts_empty(self):
        glue_object = with_request(FormSetGlue(ContactForm, **glue_context(name='contacts')))

        self.assertEqual(glue_object.get_keyed_items(), [])

    def test_initial_seeds_one_prefilled_row_per_dict(self):
        glue_object = with_request(FormSetGlue(
            ContactForm,
            initial=[{'name': 'Ada'}, {'name': 'Grace'}],
            **glue_context(name='contacts'),
        ))

        rows = glue_object.get_keyed_items()

        self.assertEqual([key for key, _ in rows], ['0', '1'])
        self.assertEqual([form.state['name']['value'] for _, form in rows], ['Ada', 'Grace'])

    def test_instances_seed_rows_bound_to_their_records_in_one_query(self):
        gorillas = [Gorilla.objects.create(name=name) for name in ('Koko', 'Harambe')]

        with self.assertNumQueries(1):
            glue_object = FormSetGlue(
                TestModelForm,
                instances=Gorilla.objects.order_by('pk'),
                **glue_context(name='gorillas'),
            )

        rows = glue_object.get_keyed_items()
        self.assertEqual(
            [form.get_identity()['target_pk'] for _, form in rows],
            [gorilla.pk for gorilla in gorillas],
        )

    def test_instances_are_ordered_before_initial_rows(self):
        gorilla = Gorilla.objects.create(name='Koko')

        glue_object = with_request(FormSetGlue(
            TestModelForm,
            initial=[{'name': 'New'}],
            instances=[gorilla],
            **glue_context(name='gorillas'),
        ))

        self.assertEqual(
            [form.state['name']['value'] for _, form in glue_object.get_keyed_items()],
            ['Koko', 'New'],
        )

    def test_model_instances_require_a_model_form(self):
        gorilla = Gorilla.objects.create(name='Koko')

        with self.assertRaisesRegex(TypeError, 'not a ModelForm'):
            FormSetGlue(ContactForm, instances=[gorilla], **glue_context(name='contacts'))

    def test_seed_beyond_max_num_is_rejected_at_construction(self):
        with self.assertRaises(GlueFormSetMaxNumExceededError):
            FormSetGlue(
                ContactForm,
                initial=[{'name': 'Ada'}, {'name': 'Grace'}],
                max_num=1,
                **glue_context(name='contacts'),
            )

    def test_instances_accept_ready_made_forms(self):
        glue_object = with_request(FormSetGlue(
            ContactForm,
            instances=[ContactForm(initial={'name': 'Ada'}), ContactForm(initial={'name': 'Grace'})],
            **glue_context(name='contacts'),
        ))

        rows = glue_object.get_keyed_items()

        self.assertEqual([key for key, _ in rows], ['0', '1'])
        self.assertEqual([form.state['name']['value'] for _, form in rows], ['Ada', 'Grace'])

    def test_instances_accept_model_forms_bound_to_their_records(self):
        gorilla = Gorilla.objects.create(name='Koko')

        glue_object = FormSetGlue(
            TestModelForm,
            instances=[TestModelForm(instance=gorilla)],
            **glue_context(name='gorillas'),
        )

        [(_, form)] = glue_object.get_keyed_items()
        self.assertEqual(form.get_identity()['target_pk'], gorilla.pk)

    def test_instances_reject_a_form_of_another_class(self):
        with self.assertRaisesRegex(TypeError, 'must be ContactForm forms'):
            FormSetGlue(ContactForm, instances=[TestModelForm()], **glue_context(name='contacts'))

    def test_instances_reject_a_bound_form(self):
        with self.assertRaisesRegex(ValueError, 'must be unbound'):
            FormSetGlue(
                ContactForm,
                instances=[ContactForm(data={'name': 'Ada'})],
                **glue_context(name='contacts'),
            )

    def test_instances_reject_another_model(self):
        with self.assertRaisesRegex(TypeError, 'must be Gorilla objects'):
            FormSetGlue(
                TestModelForm,
                instances=[Skill.objects.create(name='Climbing')],
                **glue_context(name='gorillas'),
            )

    def test_instances_reject_an_unsaved_record(self):
        with self.assertRaisesRegex(ValueError, 'must be saved'):
            FormSetGlue(TestModelForm, instances=[Gorilla(name='Koko')], **glue_context(name='gorillas'))

    def test_initial_rejects_a_non_dict_row(self):
        with self.assertRaisesRegex(TypeError, 'list of dicts'):
            FormSetGlue(ContactForm, initial=['Ada'], **glue_context(name='contacts'))

    def test_validate_reports_invalid_when_required_fields_are_missing(self):
        glue_object = with_request(FormSetGlue(ContactForm, **glue_context(name='contacts')))
        glue_object.append(key='1', initial={})

        result = glue_object.validate()

        self.assertFalse(result['valid'])
        self.assertEqual(len(result['form_list']), 1)

    def test_load_client_state_rematerializes_keyed_forms(self):
        glue_object = with_request(FormSetGlue(ContactForm, **glue_context(name='contacts')))

        glue_object._load_client_state({'forms': {
            '1': {
                'name': 'Ada',
                'email': 'ada@example.com',
                'message': 'Hello',
                'priority': 'low',
            },
        }})

        self.assertEqual(len(glue_object._forms), 1)
        key, form_glue = glue_object._forms[0]
        self.assertEqual(key, '1')
        self.assertTrue(form_glue.form.is_bound)

    def test_validate_reports_valid_when_data_is_bound_and_complete(self):
        glue_object = with_request(FormSetGlue(ContactForm, **glue_context(name='contacts')))
        glue_object._load_client_state({'forms': {
            '1': {
                'name': 'Ada',
                'email': 'ada@example.com',
                'message': 'Hello',
                'priority': 'low',
            },
        }})

        result = glue_object.validate()

        self.assertTrue(result['valid'])

    def test_clean_receives_django_forms_not_form_glues(self):
        seen: list[forms.BaseForm] = []

        class ContactFormSet(Glue.FormSet):
            form_class = ContactForm
            min_num = 1
            max_num = 5

            def clean(self, form_list):
                seen.extend(form_list)
                return []

        glue_object = with_request(ContactFormSet(**glue_context(name='contacts')))
        glue_object.append(key='1', initial={'name': 'Ada', 'email': 'ada@example.com'})

        glue_object.validate()

        self.assertEqual(len(seen), 1)
        self.assertIsInstance(seen[0], forms.BaseForm)

    def test_clean_errors_make_validation_invalid(self):
        class ContactFormSet(Glue.FormSet):
            form_class = ContactForm
            min_num = 1
            max_num = 5

            def clean(self, form_list):
                return ['Cross-form constraint failed.']

        glue_object = with_request(ContactFormSet(**glue_context(name='contacts')))
        glue_object.append(key='1', initial={'name': 'Ada', 'email': 'ada@example.com'})

        result = glue_object.validate()

        self.assertFalse(result['valid'])
        self.assertEqual(result['non_form_errors'], ['Cross-form constraint failed.'])

    def test_validate_reports_a_min_num_violation(self):
        glue_object = with_request(FormSetGlue(
            ContactForm, **glue_context(name='contacts'), min_num=2,
        ))

        result = glue_object.validate()

        self.assertFalse(result['valid'])
        self.assertEqual(result['non_form_errors'], ['Please submit at least 2 form(s).'])

    def test_validate_reports_a_max_num_violation(self):
        glue_object = with_request(FormSetGlue(
            ContactForm, **glue_context(name='contacts'), min_num=0, max_num=1,
        ))
        glue_object._load_client_state({'forms': {
            '1': {
                'name': 'Ada',
                'email': 'ada@example.com',
                'message': 'Hello',
                'priority': 'low',
            },
            '2': {
                'name': 'Bee',
                'email': 'bee@example.com',
                'message': 'Hi',
                'priority': 'low',
            },
        }})

        result = glue_object.validate()

        self.assertFalse(result['valid'])
        self.assertEqual(result['non_form_errors'], ['Please submit at most 1 form(s).'])

    def test_validate_passes_cardinality_when_within_bounds(self):
        glue_object = with_request(FormSetGlue(
            ContactForm, **glue_context(name='contacts'), min_num=1, max_num=2,
        ))
        glue_object._load_client_state({'forms': {
            '1': {
                'name': 'Ada',
                'email': 'ada@example.com',
                'message': 'Hello',
                'priority': 'low',
            },
        }})

        result = glue_object.validate()

        self.assertTrue(result['valid'])
        self.assertEqual(result['non_form_errors'], [])

    def test_reconstruct_from_policy_rebuilds_an_equivalent_formset(self):
        glue_object = with_request(FormSetGlue(
            ContactForm,
            **glue_context(name='contacts'),
            min_num=1,
            max_num=5,
            can_delete=True,
        ))
        policy = glue_object.policy

        resolved = FormSetGlue._reconstruct_from_policy(policy)

        self.assertEqual(resolved.form_class, ContactForm)
        self.assertEqual(resolved.min_num, 1)
        self.assertEqual(resolved.max_num, 5)
        self.assertTrue(resolved.can_delete)

    def test_custom_formset_clean_survives_reconstruct_round_trip(self):
        glue_object = with_request(SampleContactFormSet(**glue_context(name='contacts')))
        policy = glue_object.policy

        resolved = FormSetGlue._reconstruct_from_policy(policy)

        self.assertIsInstance(resolved, SampleContactFormSet)
        self.assertEqual(resolved.form_class, ContactForm)
        self.assertEqual(resolved.clean([ContactForm()]), ['Test cross-form error.'])

    def test_glue_formset_shortcut_from_form_class(self):
        request = with_request(FormSetGlue(ContactForm, **glue_context(name='noop'))).request

        glue_object = Glue.formset(
            target=ContactForm,
            request=request,
            unique_name='contacts',
            access=Glue.Access.CHANGE,
            min_num=2,
            max_num=10,
        )

        self.assertIsInstance(glue_object, FormSetGlue)
        self.assertEqual(glue_object.name, 'contacts')
        self.assertEqual(glue_object.form_class, ContactForm)
        self.assertEqual(glue_object.min_num, 2)
        self.assertEqual(glue_object.max_num, 10)

    def test_glue_formset_shortcut_seeds_instances_and_initial(self):
        gorilla = Gorilla.objects.create(name='Koko')

        for target in (TestModelForm, SoftDeletingGorillaFormSet):
            glue_object = with_request(Glue.formset(
                target=target,
                unique_name='gorillas',
                instances=[gorilla],
                initial=[{'name': 'New'}],
            ))

            self.assertEqual(
                [form.state['name']['value'] for _, form in glue_object.get_keyed_items()],
                ['Koko', 'New'],
            )

    def test_glue_formset_shortcut_from_custom_formset_class(self):
        class ContactFormSet(Glue.FormSet):
            form_class = ContactForm
            min_num = 1
            max_num = 5

        request = with_request(FormSetGlue(ContactForm, **glue_context(name='noop'))).request

        glue_object = Glue.formset(
            target=ContactFormSet,
            request=request,
            unique_name='contacts',
            access=Glue.Access.CHANGE,
            max_num=8,
        )

        self.assertIsInstance(glue_object, ContactFormSet)
        self.assertEqual(glue_object.form_class, ContactForm)
        self.assertEqual(glue_object.min_num, 1)
        self.assertEqual(glue_object.max_num, 8)

    def test_formset_namespace_is_registered_in_glue_class_registry(self):
        # The registry is what GlueAttributeCallResolver uses to
        # reconstruct a glue object from an incoming request's policy
        # namespace -- a class that works standalone but isn't registered
        # here still 500s on every real callable-attribute request against it.
        self.assertIs(glue_class_registry.get_glue_class('formSet'), FormSetGlue)
