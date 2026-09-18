from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from django_glue import Glue
from django_glue.access import GlueAccess
from django_glue.glue.attributes import BoundGlueAttribute, GlueAttributeCollector
from django_glue.glue.component import Component
from django_glue.glue.loading import LoadingStrategy

if TYPE_CHECKING:
    from django_glue.glue.policy import GluePolicy


class GreetingComponent(Glue.Component):
    namespace = 'greetingComponent'
    template = 'glue_template_test.html'

    def __init__(
        self,
        *,
        greeting: str = 'Hello from a component!',
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.greeting = greeting

    def get_context_data(self) -> dict[str, str]:
        return {'greeting': self.greeting}

    @classmethod
    def _reconstruct_from_policy(cls, policy: GluePolicy) -> GreetingComponent:
        return cls(
            name=policy.name,
            access=policy.access,
        )


class MissingTemplateComponent(Component):
    namespace = 'missingTemplateComponent'

    @classmethod
    def _reconstruct_from_policy(cls, policy: GluePolicy) -> MissingTemplateComponent:
        return cls(
            name=policy.name,
            access=policy.access,
        )


class ExternalState:
    def __init__(self) -> None:
        self.value = 'initial'

    def reset(self) -> str:
        self.value = 'reset'
        return self.value


class ExtendedGreetingComponent(GreetingComponent):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.external_state = ExternalState()

    def get_extra_attributes(self) -> tuple[tuple[object, dict[str, object]], ...]:
        return (
            (
                self.external_state,
                {
                    'reset': Glue.attr(ExternalState.reset),
                    'value': Glue.attr(
                        required_access=GlueAccess.CHANGE,
                        editable=True,
                    ),
                },
            ),
        )


class ChildComponent(Component):
    namespace = 'childComponent'
    template = 'glue_template_test.html'

    @classmethod
    def _reconstruct_from_policy(cls, policy: GluePolicy) -> ChildComponent:
        return cls(
            name=policy.name,
            access=policy.access,
        )


class ChildOwnerComponent(GreetingComponent):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.child_factory_calls = 0
        self.child_value: ChildComponent | None = ChildComponent()

    @Glue.property
    def child(self) -> ChildComponent:
        self.child_factory_calls += 1
        return self.child_value


class NullableChildOwnerComponent(GreetingComponent):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.child_factory_calls = 0
        self.child_value: ChildComponent | None = ChildComponent()

    @Glue.property
    def child(self) -> ChildComponent | None:
        self.child_factory_calls += 1
        return self.child_value


class DeniedChildComponent(ChildComponent):
    namespace = 'deniedChildComponent'

    def authorize(self, request: Any, operation: Any) -> bool:
        return False


class DeniedChildOwnerComponent(GreetingComponent):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.child_value = DeniedChildComponent()

    @Glue.property
    def child(self) -> DeniedChildComponent:
        return self.child_value


def test_component_is_exposed_on_glue_shortcut() -> None:
    assert Glue.Component is Component


def test_component_uses_eager_loading_by_default() -> None:
    component = GreetingComponent()

    assert component.loading_strategy == LoadingStrategy.EAGER


def test_component_accepts_template_override() -> None:
    component = GreetingComponent(template='gorilla/component/fighter_rank_card.html')

    assert component.template == 'gorilla/component/fighter_rank_card.html'


def test_component_requires_template_path() -> None:
    with pytest.raises(ValueError, match='must declare a template path'):
        MissingTemplateComponent()


def test_component_context_exposes_itself_by_default() -> None:
    component = GreetingComponent()

    assert Component.get_context_data(component) == {'component': component}


def test_component_render_requires_request_binding() -> None:
    component = GreetingComponent()

    with pytest.raises(RuntimeError, match='Cannot render unbound component'):
        component.render()


def test_component_renders_owned_template(mock_request) -> None:
    component = GreetingComponent()
    rendered_component = Glue.object(mock_request, component)

    response = rendered_component.render()

    assert response.result['is_glue_template_response'] is True
    assert 'Hello from a component!' in response.result['html']
    assert rendered_component.access == GlueAccess.VIEW


def test_component_render_is_exposed_as_glue_attribute() -> None:
    component = GreetingComponent()

    assert component.metadata['attributes']['render'] == {
        'namespace': 'callable',
        'takes_client_state': True,
    }


def test_component_collects_static_attribute_definitions() -> None:
    component = GreetingComponent()

    assert tuple(
        definition.path
        for definition in component._attribute_registry.attribute_definitions
    ) == (
        'load_state',
        'render',
    )


def test_component_collects_static_and_extra_attribute_definitions() -> None:
    component = ExtendedGreetingComponent()

    assert tuple(
        definition.path
        for definition in component._attribute_registry.attribute_definitions
    ) == (
        'load_state',
        'render',
        'reset',
        'value',
    )


def test_component_binds_extra_attributes_to_external_object() -> None:
    component = ExtendedGreetingComponent()
    attributes = {
        attribute.definition.path: attribute
        for attribute in component._attribute_registry.bind(component)
    }

    assert attributes['value'].get() == 'initial'

    attributes['value'].apply_update('changed')

    assert component.external_state.value == 'changed'
    assert not hasattr(component, 'value')
    assert attributes['reset'].call() == 'reset'
    assert component.external_state.value == 'reset'


def test_component_introduces_typed_child_at_canonical_address(mock_request) -> None:
    component = Glue.object(mock_request, ChildOwnerComponent())

    children = component._bind_children()

    assert len(children) == 1
    assert children[0].path == 'child'
    assert children[0].address.startswith(f'{component.address}.')
    assert children[0].glue_object is component.child_value
    assert children[0].glue_object.request is mock_request
    assert component.child_factory_calls == 1


def test_component_keeps_live_non_nullable_child_without_running_factory(
    mock_request,
) -> None:
    component = Glue.object(mock_request, ChildOwnerComponent())
    component.child_value = None

    children = component._bind_children(
        live_children={'child': 'root-address.existing'},
    )

    assert children[0].address == 'root-address.existing'
    assert children[0].glue_object is None
    assert component.child_factory_calls == 0


def test_component_rechecks_nullable_child_and_removes_absent_binding(
    mock_request,
) -> None:
    component = Glue.object(mock_request, NullableChildOwnerComponent())
    component.child_value = None

    children = component._bind_children(
        live_children={'child': 'root-address.existing'},
    )

    assert children == ()
    assert component.child_factory_calls == 1


def test_component_rejects_wrong_child_family(mock_request) -> None:
    component = Glue.object(mock_request, ChildOwnerComponent())
    component.child_value = GreetingComponent()

    with pytest.raises(TypeError, match='must return an unbound ChildComponent'):
        component._bind_children()


def test_component_rejects_missing_non_nullable_child(mock_request) -> None:
    component = Glue.object(mock_request, ChildOwnerComponent())
    component.child_value = None

    with pytest.raises(TypeError, match='Non-nullable Glue child'):
        component._bind_children()


def test_component_rejects_already_bound_child(mock_request) -> None:
    component = Glue.object(mock_request, ChildOwnerComponent())
    child = Glue.object(mock_request, ChildComponent())
    component.child_value = child

    with pytest.raises(ValueError, match='returned a bound Glue object'):
        component._bind_children()


def test_component_reintroduces_child_at_existing_address(mock_request) -> None:
    component = Glue.object(mock_request, ChildOwnerComponent())

    children = component._bind_children(
        live_children={'child': 'root-address.existing'},
        reintroduce=('child',),
    )

    assert children[0].address == 'root-address.existing'
    assert children[0].glue_object is component.child_value
    assert component.child_factory_calls == 1


def test_component_omits_child_denied_at_introduction(mock_request) -> None:
    component = Glue.object(mock_request, DeniedChildOwnerComponent())

    children = component._bind_children()

    assert children == ()
    assert component.child_value.request is None


@pytest.mark.parametrize(
    'result',
    [
        ChildComponent(),
        {'nested': [ChildComponent()]},
    ],
)
def test_component_rejects_glue_object_from_ordinary_value(result: object) -> None:
    class ValueOwner:
        @Glue.property
        def value(self) -> object:
            return result

    owner = ValueOwner()
    attribute = next(
        bound
        for bound in GlueAttributeCollector.collect(ValueOwner)
        if bound.path == 'value'
    )

    with pytest.raises(TypeError, match='outside an addressed child declaration'):
        BoundGlueAttribute(
            definition=attribute,
            owner=owner,
        ).get()
