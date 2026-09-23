from __future__ import annotations

import inspect
import json
from html import unescape
from typing import Any

import pytest
from django.test import RequestFactory
from django.template import Context, Template

from django_glue import Glue
from django_glue.access import GlueAccess
from django_glue.exceptions import (
    GlueComponentRegistrationError,
    GlueRequestError,
    GlueRequestErrorCode,
)
from django_glue.glue.attributes import BoundGlueAttribute, GlueAttributeCollector
from django_glue.glue.component import Component
from django_glue.glue.context import GlueContextManager
from django_glue.glue.policy import GluePolicy
from django_glue.glue.registry import glue_class_registry
from django_glue.response import GlueResponse
from django_glue.resolver.attribute_call.context import (
    AddressedObjectEntry,
    AttributeCallBatchContext,
    AttributeCallContextFactory,
)
from django_glue.resolver.attribute_call.resolver import GlueAttributeCallResolver

from django_glue.tests.glue.test_callable_parameters import call_context


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

    @Glue.attr
    def ping(self) -> str:
        return 'pong'


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


class ResolvedChildOwnerComponent(ChildOwnerComponent):
    namespace = 'resolvedChildOwnerComponent'


class MountedResultComponent(Component):
    template = 'glue_template_test.html'
    label: str = Glue.attr('initial')

    def mount(self) -> None:
        self.label = 'mounted'


class ResultProducerComponent(Component):
    template = 'glue_template_test.html'

    @Glue.attr
    def spawn(self) -> MountedResultComponent:
        return MountedResultComponent()


def test_component_is_exposed_on_glue_shortcut() -> None:
    assert Glue.Component is Component


def test_declared_parameters_are_signed_and_reconstructed_without_remount(mock_request) -> None:
    class ParameterComponent(Component):
        tag_name = 'signed-parameter-component'
        template = 'glue_template_test.html'
        count: int = Glue.attr(parameter=True)
        draft: str = Glue.attr('', parameter=True, editable=True)
        internal: str = Glue.attr('initial')

        def mount(self) -> None:
            self.internal = 'mounted'

    component = Glue.object(mock_request, ParameterComponent(count='3'))
    policy = component.policy

    assert component.count == 3
    assert policy.identity['parameters'] == {'count': 3, 'draft': ''}
    assert policy.state_snapshot == {'draft': '', 'internal': 'mounted'}

    reconstructed = Component._reconstruct_from_policy(policy)

    assert type(reconstructed) is ParameterComponent
    assert reconstructed.count == 3
    assert reconstructed.internal == 'mounted'


def test_component_returned_from_a_callable_is_mounted_at_introduction(mock_request) -> None:
    producer = Glue.object(mock_request, ResultProducerComponent())

    context = call_context(producer, 'spawn')
    reconstructed = ResultProducerComponent.from_attribute_call_resolver_context(context)
    entry, introduced = reconstructed.process_attribute_call(context)
    result_entry = next(
        introduced_entry
        for introduced_entry in introduced
        if introduced_entry['address'] == entry['result']
    )

    assert GluePolicy.from_token(result_entry['policy_token']).state_snapshot['label'] == 'mounted'


def test_component_rejects_undeclared_or_missing_parameters() -> None:
    class ParameterComponent(Component):
        tag_name = 'validation-parameter-component'
        template = 'glue_template_test.html'
        count: int = Glue.attr(parameter=True)

    with pytest.raises(Exception, match='Missing parameters'):
        ParameterComponent()
    with pytest.raises(Exception, match='Unknown parameters'):
        ParameterComponent(count=1, extra=True)


def test_component_constructor_signature_is_generated_from_declarations() -> None:
    class SignatureComponent(Component):
        tag_name = 'signature-component'
        template = 'glue_template_test.html'
        count: int = Glue.attr(parameter=True)
        note: str = Glue.attr('', parameter=True, editable=True)
        tags: list[str] = Glue.attr(default_factory=list, parameter=True)
        internal: str = Glue.attr('hidden')

    parameters = inspect.signature(SignatureComponent).parameters

    assert list(parameters) == ['name', 'template', 'access', 'count', 'note', 'tags']
    assert all(parameter.kind is inspect.Parameter.KEYWORD_ONLY for parameter in parameters.values())
    assert parameters['count'].default is inspect.Parameter.empty
    assert parameters['count'].annotation is int
    assert parameters['note'].default == ''
    assert repr(parameters['tags'].default) == '<factory>'


def test_component_template_tag_stamps_typed_keyed_components(mock_request) -> None:
    class StampedNumber(Component):
        tag_name = 'stamped-number'
        template = 'glue_template_test.html'
        number: int = Glue.attr(parameter=True)

    html = Template(
        '{% load django_glue %}{% for number in numbers %}'
        "{% glue_component 'stamped-number' number=number key=number %}"
        '{% endfor %}'
    ).render(Context({'request': mock_request, 'numbers': [1, 2]}))
    entries = GlueContextManager(mock_request).serialized_objects

    assert html.count('data-glue-address=') == 2
    assert len(entries) == 2
    assert all(GluePolicy.from_token(entry['policy_token']).identity['parameters']['number'] in {1, 2} for entry in entries)
    assert entries[0]['address'] != entries[1]['address']


def test_stamped_component_root_carries_its_children_entries(mock_request) -> None:
    class StampedChildOwner(ChildOwnerComponent):
        tag_name = 'stamped-child-owner'

    html = Template(
        "{% load django_glue %}{% glue_component 'stamped-child-owner' %}"
    ).render(Context({'request': mock_request}))
    encoded = html.split('data-glue-objects="', 1)[1].split('"', 1)[0]
    entries = json.loads(unescape(encoded))

    owner_policy = GluePolicy.from_token(entries[0]['policy_token'])
    assert entries[0]['address'] in html
    assert [entry['address'] for entry in entries[1:]] == [owner_policy.children['child']]


def test_declared_event_enters_effects_channel(mock_request) -> None:
    class EventComponent(Component):
        template = 'glue_template_test.html'
        saved = Glue.event()

    component = Glue.object(mock_request, EventComponent())
    component.saved(pk=7)

    assert component.get_static_data()['events'] == ['saved']
    assert component._effects_payload(GlueResponse(), [])['events'] == [
        {'name': 'saved', 'detail': {'pk': 7}},
    ]


def test_event_detail_rejects_a_glue_object(mock_request) -> None:
    class EventComponent(Component):
        template = 'glue_template_test.html'
        saved = Glue.event()

    component = Glue.object(mock_request, EventComponent())

    with pytest.raises(TypeError):
        component.saved(child=ChildComponent())
    with pytest.raises(ValueError, match=r'\$address'):
        component.saved(**{'$address': 'forged'})


@pytest.mark.parametrize('event_name', ['change', 'submit', 'pointerdown', 'transitionend'])
def test_event_named_like_a_dom_event_is_rejected_at_declaration(event_name: str) -> None:
    with pytest.raises((GlueComponentRegistrationError, RuntimeError)) as raised:
        type('CollidingEventComponent', (Component,), {event_name: Glue.event()})

    assert 'conflicts with a browser event' in str(raised.value.__cause__ or raised.value)


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

    assert 'Hello from a component!' in response.html
    assert rendered_component.access == GlueAccess.VIEW


def test_component_render_is_exposed_as_glue_attribute() -> None:
    component = GreetingComponent()

    assert component.get_static_data() == {
        'callables': {
            'render': {'allowed_arguments': [], 'returns_glue': False},
        },
    }


def test_component_collects_static_attribute_definitions() -> None:
    component = GreetingComponent()

    assert tuple(
        definition.path
        for definition in component._attribute_registry.attribute_definitions
    ) == (
        'render',
    )


def test_component_collects_static_and_extra_attribute_definitions() -> None:
    component = ExtendedGreetingComponent()

    assert tuple(
        definition.path
        for definition in component._attribute_registry.attribute_definitions
    ) == (
        'render',
        'reset',
        'value',
    )


def test_component_static_data_marks_editable_value_paths() -> None:
    component = ExtendedGreetingComponent()

    assert component.get_static_data()['fields']['value'] == {
        'value_path': 'value',
        'editable': True,
    }


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


def test_callless_reintroduce_entry_resigns_live_child_at_existing_address(
    mock_request,
) -> None:
    component = Glue.object(mock_request, ChildOwnerComponent())
    policy = component.policy
    child_address = policy.children['child']
    original_child_token = component._bound_children[0].glue_object.policy.token

    context = call_context(component, None, reintroduce=['child'])
    reconstructed = ChildOwnerComponent.from_attribute_call_resolver_context(context)
    entry, introduced = reconstructed.process_attribute_call(context)

    assert entry['result'] is None
    assert entry['effects'] == {'messages': []}
    assert 'policy_token' not in entry
    assert len(introduced) == 1
    reintroduction = introduced[0]
    assert reintroduction['address'] == child_address
    child_policy = GluePolicy.from_token(reintroduction['policy_token'])
    assert child_policy.address == child_address
    assert child_policy.namespace == 'childComponent'
    assert reintroduction['policy_token'] != original_child_token


def test_reintroduce_undeclared_path_fails_admission(mock_request) -> None:
    component = Glue.object(mock_request, ChildOwnerComponent())

    context = call_context(component, 'ping', reintroduce=['not_a_slot'])
    reconstructed = ChildOwnerComponent.from_attribute_call_resolver_context(context)

    with pytest.raises(GlueRequestError) as excinfo:
        reconstructed.process_attribute_call(context)
    assert excinfo.value.code == GlueRequestErrorCode.INVALID_REINTRODUCE
    assert reconstructed.child_factory_calls == 0


def test_call_and_reintroduce_advance_together(mock_request) -> None:
    component = Glue.object(mock_request, ChildOwnerComponent())
    policy = component.policy
    child_address = policy.children['child']

    context = call_context(component, 'ping', reintroduce=['child'])
    reconstructed = ChildOwnerComponent.from_attribute_call_resolver_context(context)
    entry, introduced = reconstructed.process_attribute_call(context)

    assert entry['result'] == 'pong'
    assert len(introduced) == 1
    assert introduced[0]['address'] == child_address


def test_live_child_carries_forward_without_running_factory_on_owner_call(
    mock_request,
) -> None:
    component = Glue.object(mock_request, ChildOwnerComponent())
    policy = component.policy
    child_address = policy.children['child']

    context = call_context(component, 'ping')
    reconstructed = ChildOwnerComponent.from_attribute_call_resolver_context(context)
    entry, introduced = reconstructed.process_attribute_call(context)

    assert reconstructed.child_factory_calls == 0
    assert introduced == []
    assert 'policy_token' not in entry
    assert reconstructed.policy.children == {'child': child_address}


def test_callless_entry_without_reintroduce_parses_as_a_refresh() -> None:
    request = RequestFactory().post(
        '/__dg__/callable_attribute/',
        {'objects': json.dumps([{'address': 'a#test', 'policy_token': 'token'}])},
    )

    batch = AttributeCallContextFactory(request).create()

    assert batch.entries[0].call is None
    assert batch.entries[0].reintroduce == []


def test_callless_reintroduce_entry_parses() -> None:
    request = RequestFactory().post(
        '/__dg__/callable_attribute/',
        {'objects': json.dumps([{
            'address': 'a#test',
            'policy_token': 'token',
            'reintroduce': ['child'],
        }])},
    )

    batch = AttributeCallContextFactory(request).create()

    assert batch.entries[0].call is None
    assert batch.entries[0].reintroduce == ['child']


def test_bad_reintroduce_fails_only_its_own_entry(mock_request) -> None:
    glue_class_registry.register_glue_class(ResolvedChildOwnerComponent)
    glue_class_registry.register_glue_class(GreetingComponent)
    try:
        owner_a = Glue.object(mock_request, ResolvedChildOwnerComponent())
        owner_b = Glue.object(mock_request, GreetingComponent())

        context = AttributeCallBatchContext.model_construct(
            request=mock_request,
            entries=[
                AddressedObjectEntry(
                    address=owner_a.address,
                    policy_token=owner_a.policy.token,
                    reintroduce=['not_a_slot'],
                ),
                AddressedObjectEntry(
                    address=owner_b.address,
                    policy_token=owner_b.policy.token,
                ),
            ],
        )

        response = GlueAttributeCallResolver()._resolve_json_response_from_context(context)
        objects = json.loads(response.content)['objects']
    finally:
        glue_class_registry.glue_object_classes.pop(ResolvedChildOwnerComponent.namespace)
        glue_class_registry.glue_object_classes.pop(GreetingComponent.namespace)

    assert objects[0] == {
        'address': owner_a.address,
        'error': {
            'code': 'invalid_reintroduce',
            'message': 'reintroduce names a path that is not a declared child slot.',
        },
    }
    assert objects[1]['address'] == owner_b.address
    assert 'error' not in objects[1]
    assert objects[1]['result'] is None


def test_independent_child_call_survives_owner_reintroduction(mock_request) -> None:
    glue_class_registry.register_glue_class(ResolvedChildOwnerComponent)
    glue_class_registry.register_glue_class(ChildComponent)
    try:
        owner = Glue.object(mock_request, ResolvedChildOwnerComponent())
        owner_policy = owner.policy
        child_entry = owner._serialized_child_entries()[0]
        context = AttributeCallBatchContext.model_construct(
            request=mock_request,
            entries=[
                AddressedObjectEntry(
                    address=owner.address,
                    policy_token=owner_policy.token,
                    reintroduce=['child'],
                ),
                AddressedObjectEntry(
                    address=child_entry['address'],
                    policy_token=child_entry['policy_token'],
                ),
            ],
        )

        response = GlueAttributeCallResolver()._resolve_json_response_from_context(context)
        objects = json.loads(response.content)['objects']
    finally:
        glue_class_registry.glue_object_classes.pop(ResolvedChildOwnerComponent.namespace)
        glue_class_registry.glue_object_classes.pop(ChildComponent.namespace)

    assert [entry['address'] for entry in objects] == [owner.address, child_entry['address']]
    assert objects[1]['result'] is None
    assert objects[1]['effects'] == {'messages': []}
