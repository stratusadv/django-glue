from __future__ import annotations

import datetime
import uuid
from types import SimpleNamespace

import pytest

from django_glue import Glue
from django_glue.access import GlueAccess
from django_glue.exceptions import (
    GlueComponentParameterError,
    GlueComponentRegistrationError,
)
from django_glue.glue.component.checks import check_component_tag_names
from django_glue.glue.component.object import Component
from django_glue.glue.component.registry import (
    GlueComponentRegistry,
    derive_tag_name,
    glue_component_registry,
)
from django_glue.glue.policy import GluePolicy
from django_glue.glue.registry import glue_class_registry


@pytest.fixture
def mock_request():
    return SimpleNamespace(session=SimpleNamespace(session_key='test-session'), FILES={})


class GreetingComponent(Glue.Component):
    template = 'component/greeting.html'

    greeting: str = Glue.attr(parameter=True)


class ScheduleComponent(Glue.Component):
    template = 'component/schedule.html'

    date: datetime.date = Glue.attr(parameter=True)
    user_id: int = Glue.attr(parameter=True)


class RenamedComponent(Glue.Component):
    template = 'component/renamed.html'
    tag_name = 'time-tracker.renamed-thing'

    label: str = Glue.attr(parameter=True)


class OptionalParameterComponent(Glue.Component):
    template = 'component/optional.html'

    note: str | None = Glue.attr(parameter=True)


class SharedBase(Glue.Component):
    """An intermediate base declaring no template is not stampable."""


def test_subclassing_registers_the_component() -> None:
    assert glue_component_registry.get('greeting-component') is GreetingComponent


def test_tag_name_is_derived_from_the_class_name() -> None:
    assert GreetingComponent.tag_name == 'greeting-component'
    assert ScheduleComponent.tag_name == 'schedule-component'
    assert derive_tag_name(ScheduleComponent) == 'schedule-component'


def test_explicit_tag_name_overrides_the_derived_one() -> None:
    assert RenamedComponent.tag_name == 'time-tracker.renamed-thing'
    assert glue_component_registry.get('time-tracker.renamed-thing') is RenamedComponent


def test_templateless_base_claims_no_tag_name() -> None:
    assert SharedBase.tag_name is None
    assert 'shared-base' not in glue_component_registry


def test_components_share_one_class_registry_namespace() -> None:
    assert Component.namespace == 'component'
    assert GreetingComponent.namespace == 'component'
    assert glue_class_registry.get_glue_class('component') is Component


def test_unregistered_tag_name_fails_closed() -> None:
    with pytest.raises(GlueComponentRegistrationError, match='No Glue component is registered'):
        glue_component_registry.get('never-declared')


def test_invalid_tag_name_is_rejected() -> None:
    with pytest.raises(GlueComponentRegistrationError, match='kebab-case'):
        class BadName(Glue.Component):
            template = 'component/bad.html'
            tag_name = 'Not Kebab Case'


def test_component_is_exposed_on_the_glue_shortcut() -> None:
    assert Glue.Component is Component


class TestAutodiscovery:
    """Discovery must be exhaustive, not best-effort.

    A component nobody imports registers only if some unrelated view happens to
    import its module. Stamping then works and reconstruction on the next
    request fails, so the bug reproduces inconsistently and points elsewhere.
    """

    def test_component_module_in_an_app_is_discovered(self) -> None:
        from test_project.gorilla.components.gorilla_card import GorillaCard

        assert glue_component_registry.get('gorilla-card') is GorillaCard

    def test_submodule_is_discovered_without_a_re_export(self) -> None:
        """components/__init__.py is empty; the walk finds the submodule."""
        import test_project.gorilla.components as package

        assert package.__doc__ is None
        assert not hasattr(package, 'GorillaCard')
        assert 'gorilla-card' in glue_component_registry

    def test_walk_recurses_into_nested_subpackages(self) -> None:
        from test_project.gorilla.components.cards.fighter_card import FighterCard

        assert glue_component_registry.get('fighter-card') is FighterCard


class TestParameters:
    def test_declared_parameters_are_accepted(self) -> None:
        component = ScheduleComponent(date=datetime.date(2026, 9, 9), user_id=5)

        assert component.date == datetime.date(2026, 9, 9)
        assert component.user_id == 5

    def test_undeclared_parameter_is_rejected(self) -> None:
        with pytest.raises(GlueComponentParameterError, match='undeclared'):
            ScheduleComponent(date=datetime.date(2026, 9, 9), user_id=5, total_hours=8)

    def test_missing_parameter_is_rejected(self) -> None:
        with pytest.raises(GlueComponentParameterError, match='requires'):
            ScheduleComponent(date=datetime.date(2026, 9, 9))

    def test_parameters_appear_in_the_generated_signature(self) -> None:
        signature = ScheduleComponent.__signature__

        assert list(signature.parameters) == ['date', 'user_id']
        assert signature.parameters['date'].annotation is datetime.date

    def test_unannotated_parameter_is_rejected_at_declaration(self) -> None:
        with pytest.raises(GlueComponentParameterError, match='no type annotation'):
            class Unannotated(Glue.Component):
                template = 'component/unannotated.html'
                whatever = Glue.attr(parameter=True)

    def test_unserializable_annotation_is_rejected_at_declaration(self) -> None:
        with pytest.raises(GlueComponentParameterError, match='cannot round-trip'):
            class Unserializable(Glue.Component):
                template = 'component/unserializable.html'
                items: list = Glue.attr(parameter=True)

    def test_parameter_implies_identity(self) -> None:
        options = ScheduleComponent.__dict__['date'].__glue_options__

        assert options.is_parameter is True
        assert options.is_identity is True


class TestIdentityAndReconstruction:
    def _policy(self, component, mock_request) -> GluePolicy:
        component.request = mock_request
        return GluePolicy.from_glue_object(glue_object=component)

    def test_identity_signs_the_tag_name_and_parameters(self, mock_request) -> None:
        component = ScheduleComponent(
            name='schedule',
            date=datetime.date(2026, 9, 9),
            user_id=5,
        )
        policy = self._policy(component, mock_request)

        assert policy.identity['tag_name'] == 'schedule-component'
        assert policy.identity['user_id'] == 5

    def test_reconstruction_resolves_the_concrete_class(self, mock_request) -> None:
        component = ScheduleComponent(
            name='schedule',
            date=datetime.date(2026, 9, 9),
            user_id=5,
        )
        policy = self._policy(component, mock_request)

        reconstructed = Component._reconstruct_from_policy(policy)

        assert type(reconstructed) is ScheduleComponent
        assert reconstructed.name == 'schedule'

    def test_reconstruction_coerces_parameters_back_to_their_annotation(
        self,
        mock_request,
    ) -> None:
        """A date must not come back as the string JSON decoded it to."""
        component = ScheduleComponent(
            name='schedule',
            date=datetime.date(2026, 9, 9),
            user_id=5,
        )
        policy = self._policy(component, mock_request)

        assert policy.identity['date'] == '2026-09-09'

        reconstructed = Component._reconstruct_from_policy(policy)

        assert reconstructed.date == datetime.date(2026, 9, 9)
        assert isinstance(reconstructed.date, datetime.date)
        assert isinstance(reconstructed.user_id, int)

    def test_reconstruction_preserves_access(self, mock_request) -> None:
        component = ScheduleComponent(
            name='schedule',
            access=GlueAccess.CHANGE,
            date=datetime.date(2026, 9, 9),
            user_id=5,
        )
        policy = self._policy(component, mock_request)

        assert Component._reconstruct_from_policy(policy).access == GlueAccess.CHANGE

    def test_reconstruction_rejects_a_policy_without_a_tag_name(self, mock_request) -> None:
        component = ScheduleComponent(
            name='schedule',
            date=datetime.date(2026, 9, 9),
            user_id=5,
        )
        policy = self._policy(component, mock_request)
        policy.identity.pop('tag_name')

        with pytest.raises(GlueComponentRegistrationError, match='no tag_name'):
            Component._reconstruct_from_policy(policy)

    def test_optional_parameter_round_trips_none(self, mock_request) -> None:
        component = OptionalParameterComponent(name='optional', note=None)
        policy = self._policy(component, mock_request)

        assert Component._reconstruct_from_policy(policy).note is None


class TestMount:
    def test_mount_runs_on_introduction(self, mock_request) -> None:
        class Mounting(Glue.Component):
            template = 'component/mounting.html'

            seed: int = Glue.attr(parameter=True)

            def mount(self) -> None:
                self.mounted = True

        component = Mounting(seed=1).introduce(mock_request)

        assert component.mounted is True
        assert component.request is mock_request

    def test_mount_does_not_run_on_reconstruction(self, mock_request) -> None:
        class NotRemounting(Glue.Component):
            template = 'component/not_remounting.html'

            seed: int = Glue.attr(parameter=True)

            def mount(self) -> None:
                self.mounted = True

        component = NotRemounting(name='seeded', seed=1).introduce(mock_request)
        policy = GluePolicy.from_glue_object(glue_object=component)

        reconstructed = Component._reconstruct_from_policy(policy)

        assert getattr(reconstructed, 'mounted', False) is False
        assert reconstructed._is_reconstructed is True


class TestRendering:
    def test_root_attributes_carry_the_binding_and_the_marker(self, mock_request) -> None:
        component = GreetingComponent(name='greeter', greeting='hi')
        component.request = mock_request

        attributes = component.root_attributes

        assert ' x-data="{ component: Glue.component.greeter }"' in attributes
        assert ' data-glue="greeter"' in attributes

    def test_root_attributes_carry_the_component_manifest(self, mock_request) -> None:
        """A component's policy rides on its own root, not in the page's
        manifest_list, which is serialized before the body is stamped."""
        component = GreetingComponent(name='greeter', greeting='hi')
        component.request = mock_request

        assert 'data-glue-manifest="' in component.root_attributes
        assert 'is_glue_manifest' in component.root_attributes

    def test_the_proxy_is_bound_under_the_same_name_the_template_context_uses(
        self,
    ) -> None:
        """An attribute is spelled the same server-side and client-side.

        {{ component.name }} renders it; x-text="component.name" binds it.
        """
        component = GreetingComponent(name='greeter', greeting='hi')

        assert component.alpine_binding == '{ component: Glue.component.greeter }'
        assert 'component' in component.get_context_data()

    def test_the_context_exposes_only_the_component(self) -> None:
        """A component template is ordinary HTML; it carries no Glue marker."""
        component = GreetingComponent(name='greeter', greeting='hi')

        assert component.get_context_data() == {'component': component}

    def test_render_requires_a_bound_request(self) -> None:
        component = GreetingComponent(name='greeter', greeting='hi')

        with pytest.raises(GlueComponentRegistrationError, match='unbound'):
            component.render()

    def test_render_is_exposed_as_a_glue_attribute(self, mock_request) -> None:
        component = GreetingComponent(name='greeter', greeting='hi')
        component.request = mock_request

        assert 'render' in component.attributes


class TestDuplicateTagNames:
    def test_collision_is_recorded_rather_than_raised(self) -> None:
        registry = GlueComponentRegistry()

        class First(Component):
            template = 'component/first.html'

        class Second(Component):
            template = 'component/second.html'

        registry.register(First, 'shared-tag')
        registry.register(Second, 'shared-tag')

        assert registry.get('shared-tag') is First
        assert len(registry.collisions) == 1
        assert registry.collisions[0][0] == 'shared-tag'

    def test_reregistering_the_same_class_is_not_a_collision(self) -> None:
        """Django's autoreloader re-imports modules; that is not a conflict."""
        registry = GlueComponentRegistry()

        class Reloaded(Component):
            template = 'component/reloaded.html'

        registry.register(Reloaded, 'reloaded')
        registry.register(Reloaded, 'reloaded')

        assert registry.collisions == []

    def test_the_system_check_reports_collisions(self, monkeypatch) -> None:
        registry = GlueComponentRegistry()
        registry.collisions.append(('shared-tag', 'a.First', 'b.Second'))
        monkeypatch.setattr(
            'django_glue.glue.component.checks.glue_component_registry',
            registry,
        )

        errors = check_component_tag_names()

        assert len(errors) == 1
        assert errors[0].id == 'django_glue.E001'
        assert 'shared-tag' in errors[0].msg

    def test_the_system_check_is_silent_without_collisions(self) -> None:
        assert check_component_tag_names() == []


class TestParameterCoercionTypes:
    @pytest.mark.parametrize(
        ('annotation', 'value', 'expected'),
        [
            (datetime.date, '2026-09-09', datetime.date(2026, 9, 9)),
            (int, '5', 5),
            (bool, 'true', True),
            (uuid.UUID, '0b7f1a1e-0000-4000-8000-000000000000',
             uuid.UUID('0b7f1a1e-0000-4000-8000-000000000000')),
        ],
    )
    def test_decoded_values_coerce_to_their_annotation(
        self,
        annotation,
        value,
        expected,
    ) -> None:
        from django_glue.glue.component.parameters import coerce_parameter

        assert coerce_parameter('field', value, annotation, 'Owner') == expected

    def test_uncoercible_value_names_the_parameter(self) -> None:
        from django_glue.glue.component.parameters import coerce_parameter

        with pytest.raises(GlueComponentParameterError, match="'field'"):
            coerce_parameter('field', 'not-a-date', datetime.date, 'Owner')

    def test_none_for_a_required_parameter_is_rejected(self) -> None:
        from django_glue.glue.component.parameters import coerce_parameter

        with pytest.raises(GlueComponentParameterError, match='not optional'):
            coerce_parameter('field', None, datetime.date, 'Owner')
