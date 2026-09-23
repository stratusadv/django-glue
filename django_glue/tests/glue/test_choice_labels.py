from __future__ import annotations

from django import forms
from django.template.response import TemplateResponse
from django.test import TestCase

from django_glue import Glue
from django_glue.glue import FormGlue
from django_glue.glue.options.django import GlueRelatedModelChoices
from django_glue.tests.glue.test_objects import glue_context, with_request
from test_project.gorilla.models import Skill


def skill_label_formatter(skill: Skill) -> str:
    return f'{skill.name} (difficulty {skill.difficulty})'


def skill_label_template_string(skill: Skill) -> str:
    return 'pre {% if 1 %}mid{% endif %} post'


def skill_label_formatter_html(request, skill: Skill) -> TemplateResponse:
    return TemplateResponse(request, 'choice_label_test.html', {'skill': skill})


def skill_label_formatter_bad_return(skill: Skill) -> int:
    return 42


def skill_label_three_arguments(request, skill: Skill, extra) -> str:
    return skill.name


class FormattedSkillForm(forms.Form):
    skill = forms.ModelChoiceField(queryset=Glue.choices(
        Skill.objects.all(),
        label_formatter=skill_label_formatter,
    ))


def skill_form_glue(queryset, *, initial=None) -> FormGlue:
    class SkillForm(forms.Form):
        skill = forms.ModelChoiceField(queryset=queryset)

    glue_object = with_request(FormGlue(
        SkillForm(initial=initial or {}),
        **glue_context(name='skill-form'),
    ))
    return glue_object


class ChoiceLabelFormatterTestCase(TestCase):
    def test_string_result_renders_label_and_keeps_str_on_obj(self):
        Skill.objects.create(name='Grappling', difficulty=3)
        glue_object = skill_form_glue(Glue.choices(
            Skill.objects.all(),
            label_formatter=skill_label_formatter,
        ))

        result = glue_object.foreign_key_choices(field_name='skill')

        self.assertEqual(result['results'][0]['label'], 'Grappling (difficulty 3)')
        self.assertEqual(result['results'][0]['obj']['__str__'], 'Grappling')

    def test_string_result_is_rendered_as_template(self):
        Skill.objects.create(name='Grappling')
        glue_object = skill_form_glue(Glue.choices(
            Skill.objects.all(),
            label_formatter=skill_label_template_string,
        ))

        result = glue_object.foreign_key_choices(field_name='skill')

        self.assertEqual(result['results'][0]['label'], 'pre mid post')

    def test_request_taking_formatter_renders_template_response(self):
        Skill.objects.create(name='Grappling')
        glue_object = skill_form_glue(Glue.choices(
            Skill.objects.all(),
            label_formatter=skill_label_formatter_html,
        ))

        result = glue_object.foreign_key_choices(field_name='skill')

        self.assertEqual(result['results'][0]['label'].strip(), '<b>Grappling</b>')

    def test_callable_is_stored_as_its_dotted_path(self):
        options = GlueRelatedModelChoices(Glue.choices(
            Skill.objects.all(),
            label_formatter=skill_label_formatter,
        )).explicit_options

        self.assertEqual(
            options.label_formatter,
            f'{skill_label_formatter.__module__}.skill_label_formatter',
        )

    def test_dotted_path_is_stored_and_resolved(self):
        Skill.objects.create(name='Grappling', difficulty=5)
        glue_object = skill_form_glue(Glue.choices(
            Skill.objects.all(),
            label_formatter='django_glue.tests.glue.test_choice_labels.skill_label_formatter',
        ))

        result = glue_object.foreign_key_choices(field_name='skill')

        self.assertEqual(result['results'][0]['label'], 'Grappling (difficulty 5)')

    def test_formatter_survives_policy_reconstruction(self):
        Skill.objects.create(name='Grappling', difficulty=2)
        glue_object = with_request(FormGlue(
            FormattedSkillForm(),
            **glue_context(name='skill-form'),
        ))

        restored = FormGlue._reconstruct_from_policy(glue_object.policy)
        restored.request = glue_object.request

        result = restored.foreign_key_choices(field_name='skill')

        self.assertEqual(result['results'][0]['label'], 'Grappling (difficulty 2)')

    def test_rejects_invalid_formatters(self):
        with self.assertRaises(TypeError):
            Glue.choices(Skill.objects.all(), label_formatter=42)

        with self.assertRaises(ValueError):
            Glue.choices(Skill.objects.all(), label_formatter='nonexistent.module.path')

        with self.assertRaises(ValueError):
            Glue.choices(Skill.objects.all(), label_formatter='django.db.models')

        with self.assertRaisesRegex(ValueError, 'importable by its dotted path'):
            Glue.choices(Skill.objects.all(), label_formatter=lambda skill: skill.name)

        with self.assertRaisesRegex(TypeError, 'must accept'):
            Glue.choices(
                Skill.objects.all(),
                label_formatter=skill_label_three_arguments,
            )

        with self.assertRaises(TypeError):
            Glue.choices([('a', 'A')], label_formatter=skill_label_formatter)

    def test_rejects_invalid_return_type(self):
        Skill.objects.create(name='Grappling')
        glue_object = skill_form_glue(Glue.choices(
            Skill.objects.all(),
            label_formatter=skill_label_formatter_bad_return,
        ))

        with self.assertRaisesRegex(TypeError, 'must return a string or a TemplateResponse'):
            glue_object.foreign_key_choices(field_name='skill')

    def test_choices_carry_has_html_label_only_with_a_formatter(self):
        Skill.objects.create(name='Grappling')
        formatted = skill_form_glue(Glue.choices(
            Skill.objects.all(),
            label_formatter=skill_label_formatter,
        ))
        plain = skill_form_glue(Skill.objects.all())

        self.assertTrue(
            formatted.foreign_key_choices(field_name='skill')['results'][0]['has_html_label']
        )
        self.assertNotIn(
            'has_html_label',
            plain.foreign_key_choices(field_name='skill')['results'][0],
        )

    def test_selected_choice_uses_formatted_label(self):
        selected = Skill.objects.create(name='Grappling', difficulty=3)
        glue_object = skill_form_glue(
            Glue.choices(
                Skill.objects.all(),
                search_fields=['name'],
                label_formatter=skill_label_formatter,
            ),
            initial={'skill': selected.pk},
        )

        computed = glue_object.attributes['skill'].computed_data()

        self.assertEqual(computed['selected_choice']['label'], 'Grappling (difficulty 3)')
        self.assertTrue(computed['selected_choice']['has_html_label'])


class SearchableChoiceSourceTestCase(TestCase):
    def test_unfiltered_load_returns_the_first_page_in_queryset_order(self):
        skills = [Skill.objects.create(name=f'Skill {index}') for index in range(3)]
        glue_object = skill_form_glue(Glue.choices(
            Skill.objects.all().order_by('-name'),
            search_fields=['name'],
            search_limit=2,
        ))

        result = glue_object.foreign_key_choices(field_name='skill')

        self.assertEqual(
            [choice['value'] for choice in result['results']],
            [skill.pk for skill in sorted(skills, key=lambda skill: skill.name, reverse=True)[:2]],
        )

    def test_search_fields_default_to_fields(self):
        options = GlueRelatedModelChoices(Glue.choices(
            Skill.objects.all(),
            fields=['name', 'description'],
        )).explicit_options

        self.assertEqual(options.search_fields, ('name', 'description'))
        self.assertEqual(options.fields, ('name', 'description'))

    def test_explicit_search_fields_are_not_replaced_by_fields(self):
        options = GlueRelatedModelChoices(Glue.choices(
            Skill.objects.all(),
            search_fields=['name'],
            fields=['name', 'description'],
        )).explicit_options

        self.assertEqual(options.search_fields, ('name',))

    def test_fields_only_source_is_searchable_on_every_field(self):
        description_match = Skill.objects.create(name='Guard', description='Defence skill')
        Skill.objects.create(name='Striking', description='Offence')
        glue_object = skill_form_glue(Glue.choices(
            Skill.objects.all(),
            fields=['name', 'description'],
        ))

        self.assertTrue(glue_object.attributes['skill'].schema()['choices_searchable'])
        result = glue_object.foreign_key_choices(field_name='skill', search='defence')

        self.assertEqual(
            [choice['value'] for choice in result['results']],
            [description_match.pk],
        )

    def test_fields_only_sliced_queryset_is_rejected(self):
        with self.assertRaises(ValueError):
            Glue.choices(Skill.objects.all()[:5], fields=['name'])
