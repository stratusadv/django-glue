from __future__ import annotations

import inspect
from dataclasses import FrozenInstanceError
from typing import TYPE_CHECKING

import pytest

from django_glue import Glue
from django_glue.access import GlueAccess
from django_glue.glue.attributes.collector import GlueAttributeCollector
from django_glue.glue.attributes.definition import (
    BoundGlueAttribute,
    GlueAttributeDefinition,
    GlueAttributeKind,
    GlueValueRole,
)
from django_glue.glue.attributes.registry import GlueAttributeRegistry
from django_glue.glue.base import BaseGlue
from django_glue.glue.component import Component

if TYPE_CHECKING:
    from django_glue.glue.attributes.declared import DeclaredAttributeOptions


class RoleDeclarations:
    parameterized_reconstructor = Glue.attr(parameter=True)
    internal_reconstructor = Glue.attr(0)
    parameterized_editable_state = Glue.attr(
        '',
        parameter=True,
        editable=True,
    )
    internal_editable_state = Glue.attr('', editable=True)

    @Glue.property
    def derived_output(self) -> str:
        return 'derived'

    @Glue.attr
    def callable_member(self) -> None:
        return None


def options_for(name: str) -> DeclaredAttributeOptions:
    declaration = inspect.getattr_static(RoleDeclarations, name)
    return declaration.__glue_options__


def test_parameter_is_independent_from_reconstructor_role() -> None:
    parameterized = options_for('parameterized_reconstructor')
    internal = options_for('internal_reconstructor')

    assert parameterized.value_role == GlueValueRole.RECONSTRUCTOR
    assert parameterized.is_parameter
    assert internal.value_role == GlueValueRole.RECONSTRUCTOR
    assert not internal.is_parameter


def test_parameter_is_independent_from_editable_state_role() -> None:
    parameterized = options_for('parameterized_editable_state')
    internal = options_for('internal_editable_state')

    assert parameterized.value_role == GlueValueRole.EDITABLE_STATE
    assert parameterized.is_parameter
    assert internal.value_role == GlueValueRole.EDITABLE_STATE
    assert not internal.is_parameter


def test_component_parameter_is_a_shortcut_for_attr_parameter() -> None:
    assert (
        Glue.ComponentParameter().__glue_options__
        == Glue.attr(parameter=True).__glue_options__
    )
    assert (
        Glue.ComponentParameter('', editable=True).__glue_options__
        == Glue.attr('', parameter=True, editable=True).__glue_options__
    )


def test_parameter_on_non_component_glue_object_raises() -> None:
    with pytest.raises(RuntimeError) as exc_info:

        class NonComponentParameterGlue(BaseGlue):
            namespace = 'nonComponentParameter'
            param = Glue.ComponentParameter(0)

    underlying = exc_info.value.__cause__ or exc_info.value.__context__
    assert isinstance(underlying, TypeError)
    assert 'only valid on Glue.Component' in str(underlying)


def test_parameter_on_component_glue_object_is_allowed() -> None:
    class ParameterAllowedComponent(Component):
        tag_name = 'parameter-allowed-component'
        template = 'glue_template_test.html'

        week: int = Glue.ComponentParameter(0)

    assert issubclass(ParameterAllowedComponent, Component)
    assert 'week' in ParameterAllowedComponent._declared_parameters()


def test_property_is_derived_output() -> None:
    options = options_for('derived_output')

    assert options.value_role == GlueValueRole.DERIVED_OUTPUT
    assert not options.is_parameter


def test_callable_declaration_has_no_value_role() -> None:
    options = options_for('callable_member')

    assert options.is_callable
    assert options.value_role is None
    assert not options.is_parameter


@pytest.mark.parametrize(
    'role_option',
    [
        'parameter',
        'editable',
    ],
)
def test_callable_cannot_declare_value_options(role_option: str) -> None:
    with pytest.raises(
        TypeError,
        match=f'{role_option}=True is only valid for value declarations',
    ):
        Glue.attr(
            lambda: None,
            **{role_option: True},
        )


def definition_for(name: str) -> GlueAttributeDefinition:
    registry = GlueAttributeRegistry(
        GlueAttributeCollector.collect(RoleDeclarations)
    )
    definition = registry.get(name)
    assert definition is not None
    return definition


def test_declarations_compile_to_ordered_attribute_definitions() -> None:
    registry = GlueAttributeRegistry(
        GlueAttributeCollector.collect(RoleDeclarations)
    )

    assert tuple(definition.path for definition in registry.attribute_definitions) == (
        'callable_member',
        'derived_output',
        'internal_editable_state',
        'internal_reconstructor',
        'parameterized_editable_state',
        'parameterized_reconstructor',
    )
    assert definition_for('callable_member').kind == GlueAttributeKind.CALLABLE
    assert definition_for('derived_output').kind == GlueAttributeKind.VALUE
    assert definition_for('derived_output').value_role == GlueValueRole.DERIVED_OUTPUT
    assert definition_for('parameterized_editable_state').is_parameter


def test_registry_orders_attribute_definitions_by_path() -> None:
    class LaterDeclarations:
        zulu = Glue.attr(0)

    class EarlierDeclarations:
        alpha = Glue.attr(0)

    registry = GlueAttributeRegistry((
        *GlueAttributeCollector.collect(LaterDeclarations),
        *GlueAttributeCollector.collect(EarlierDeclarations),
    ))

    assert tuple(
        definition.path
        for definition in registry.attribute_definitions
    ) == ('alpha', 'zulu')


def test_attribute_compilation_does_not_invoke_descriptors() -> None:
    class ExplodingDescriptor:
        def __get__(
            self,
            instance: object | None,
            owner: type[object] | None = None,
        ) -> object:
            raise AssertionError('descriptor executed during compilation')

    class StaticDeclarations:
        value = Glue.attr(ExplodingDescriptor())

    registry = GlueAttributeRegistry(
        GlueAttributeCollector.collect(StaticDeclarations)
    )

    assert registry.get('value') is not None
    assert registry.get('value').kind == GlueAttributeKind.VALUE


def test_bound_attribute_applies_only_editable_updates() -> None:
    declarations = RoleDeclarations()
    registry = GlueAttributeRegistry(
        GlueAttributeCollector.collect(RoleDeclarations)
    )
    attributes = {
        attribute.definition.path: attribute
        for attribute in registry.bind(declarations)
    }

    attributes['internal_editable_state'].apply_update('changed')

    assert declarations.internal_editable_state == 'changed'
    with pytest.raises(TypeError, match='does not accept client updates'):
        attributes['internal_reconstructor'].apply_update(5)
    assert declarations.internal_reconstructor == 0


def test_bound_attribute_is_immutable() -> None:
    attribute = BoundGlueAttribute(
        definition=definition_for('internal_reconstructor'),
        owner=RoleDeclarations(),
    )

    with pytest.raises(FrozenInstanceError):
        attribute.owner = object()


class FunctionProvider:
    @Glue.attr
    def send(self) -> None:
        return None


class BaseConstructorLike:
    def __init__(self, target: object) -> None:
        self.target = target

    def __get__(self, instance: object, owner: type | None = None) -> object:
        return self


def test_namespace_compiles_full_capability_paths() -> None:
    class FactoryProvider:
        @Glue.attr(required_access=GlueAccess.CHANGE)
        def duplicate(self) -> None:
            return None

    class ServicesProvider:
        factory = Glue.namespace(FactoryProvider)

        @Glue.attr
        def reset(self) -> None:
            return None

    class NamespacedOwner:
        services = Glue.namespace(ServicesProvider)

    registry = GlueAttributeRegistry(
        GlueAttributeCollector.collect(NamespacedOwner)
    )

    assert tuple(definition.path for definition in registry) == (
        'services',
        'services.factory',
        'services.factory.duplicate',
        'services.reset',
    )
    assert registry.get('services').kind == GlueAttributeKind.NAMESPACE
    assert registry.get('services').provider_type is ServicesProvider
    assert registry.get('services.factory').kind == GlueAttributeKind.NAMESPACE
    assert registry.get('services.factory').provider_type is FactoryProvider
    assert registry.get('services.factory.duplicate').kind == GlueAttributeKind.CALLABLE
    assert registry.get('services.factory.duplicate').required_access == GlueAccess.CHANGE
    assert registry.get('services.reset').kind == GlueAttributeKind.CALLABLE
    assert registry.get('services.reset').required_access == GlueAccess.VIEW


def test_namespace_descriptor_form_uses_prototype_type() -> None:
    class DescriptorProvider:
        @Glue.attr
        def ping(self) -> None:
            return None

        def __get__(
            self,
            instance: object | None,
            owner: type | None = None,
        ) -> object:
            return self

    class DescriptorNamedOwner:
        services = Glue.namespace(DescriptorProvider())

    registry = GlueAttributeRegistry(
        GlueAttributeCollector.collect(DescriptorNamedOwner)
    )

    assert registry.get('services').kind == GlueAttributeKind.NAMESPACE
    assert registry.get('services').provider_type is DescriptorProvider
    assert registry.get('services.ping').kind == GlueAttributeKind.CALLABLE


def test_namespace_class_form_compiles_static_type() -> None:
    class ClassProvider:
        @Glue.attr
        def ping(self) -> None:
            return None

    class ClassNamedOwner:
        services = Glue.namespace(ClassProvider)

    registry = GlueAttributeRegistry(
        GlueAttributeCollector.collect(ClassNamedOwner)
    )

    assert registry.get('services').kind == GlueAttributeKind.NAMESPACE
    assert registry.get('services').provider_type is ClassProvider
    assert registry.get('services.ping').kind == GlueAttributeKind.CALLABLE


def test_namespace_function_form_uses_return_annotation() -> None:
    class FunctionNamedOwner:
        @Glue.namespace
        def services(self) -> FunctionProvider:
            return FunctionProvider()

    registry = GlueAttributeRegistry(
        GlueAttributeCollector.collect(FunctionNamedOwner)
    )

    assert registry.get('services').kind == GlueAttributeKind.NAMESPACE
    assert registry.get('services').provider_type is FunctionProvider
    assert registry.get('services.send').kind == GlueAttributeKind.CALLABLE


def test_namespace_rejects_plain_non_descriptor_instance() -> None:
    class PlainService:
        def do(self) -> None:
            return None

    with pytest.raises(TypeError, match='descriptor or a class'):
        Glue.namespace(PlainService())


def test_namespace_function_form_requires_return_annotation() -> None:
    def unnamed(_self: object) -> None:
        return None

    with pytest.raises(TypeError, match='return annotation'):
        Glue.namespace(unnamed)


def test_namespace_provider_cycle_is_compile_error() -> None:
    class SelfReferencingProvider:
        pass

    SelfReferencingProvider.nested = Glue.namespace(SelfReferencingProvider)

    class SelfCycleOwner:
        services = Glue.namespace(SelfReferencingProvider)

    with pytest.raises(ValueError, match='cycles through'):
        GlueAttributeRegistry(
            GlueAttributeCollector.collect(SelfCycleOwner)
        )


def test_typed_property_compiles_child_slot() -> None:
    class PanelOwner:
        @Glue.property
        def panel(self) -> Component:
            return Component(template='panel.html')

    registry = GlueAttributeRegistry(
        GlueAttributeCollector.collect(PanelOwner)
    )
    definition = registry.get('panel')

    assert definition is not None
    assert definition.kind == GlueAttributeKind.CHILD
    assert definition.expected_type is Component
    assert not definition.is_nullable


def test_nullable_child_property_compiles_nullable_slot() -> None:
    class PanelOwner:
        @Glue.property
        def panel(self) -> Component | None:
            return None

    registry = GlueAttributeRegistry(
        GlueAttributeCollector.collect(PanelOwner)
    )
    definition = registry.get('panel')

    assert definition is not None
    assert definition.kind == GlueAttributeKind.CHILD
    assert definition.expected_type is Component
    assert definition.is_nullable


def test_callable_compiles_glue_result_contract() -> None:
    class PanelOwner:
        @Glue.attr
        def panel(self) -> Component:
            return Component(template='panel.html')

        @Glue.attr
        def optional_panel(self) -> Component | None:
            return None

    registry = GlueAttributeRegistry(
        GlueAttributeCollector.collect(PanelOwner)
    )
    panel = registry.get('panel')
    optional_panel = registry.get('optional_panel')

    assert panel is not None
    assert panel.kind == GlueAttributeKind.CALLABLE
    assert panel.expected_type is Component
    assert not panel.is_nullable
    assert optional_panel is not None
    assert optional_panel.expected_type is Component
    assert optional_panel.is_nullable


def test_generic_property_annotation_does_not_compile_child_slot() -> None:
    class PanelOwner:
        @Glue.property
        def panels(self) -> list[Component]:
            return []

    registry = GlueAttributeRegistry(
        GlueAttributeCollector.collect(PanelOwner)
    )
    definition = registry.get('panels')

    assert definition is not None
    assert definition.kind == GlueAttributeKind.VALUE
    assert definition.expected_type is None
    assert not definition.is_nullable


def test_plain_property_is_not_a_child_slot() -> None:
    definition = definition_for('derived_output')

    assert definition.kind == GlueAttributeKind.VALUE
    assert definition.expected_type is None
    assert not definition.is_nullable


def test_registry_rejects_path_crossing_non_namespace() -> None:
    value = GlueAttributeDefinition(
        path='services',
        source_name='services',
        kind=GlueAttributeKind.VALUE,
        required_access=GlueAccess.VIEW,
        value_role=GlueValueRole.RECONSTRUCTOR,
    )
    leaf = GlueAttributeDefinition(
        path='services.ping',
        source_name='ping',
        kind=GlueAttributeKind.CALLABLE,
        required_access=GlueAccess.VIEW,
    )

    with pytest.raises(ValueError, match='non-namespace prefix'):
        GlueAttributeRegistry((value, leaf))


def test_registry_rejects_missing_namespace_prefix() -> None:
    leaf = GlueAttributeDefinition(
        path='services.ping',
        source_name='ping',
        kind=GlueAttributeKind.CALLABLE,
        required_access=GlueAccess.VIEW,
    )

    with pytest.raises(ValueError, match='requires namespace prefix'):
        GlueAttributeRegistry((leaf,))


def test_registry_rejects_duplicate_paths_across_collectors() -> None:
    class FirstDeclarations:
        value = Glue.attr(0)

    class SecondDeclarations:
        value = Glue.attr(1)

    with pytest.raises(ValueError, match='paths must be unique'):
        GlueAttributeRegistry((
            *GlueAttributeCollector.collect(FirstDeclarations),
            *GlueAttributeCollector.collect(SecondDeclarations),
        ))


def test_namespace_definition_requires_provider_type() -> None:
    with pytest.raises(ValueError, match='requires a provider type'):
        GlueAttributeDefinition(
            path='services',
            source_name='services',
            kind=GlueAttributeKind.NAMESPACE,
            required_access=GlueAccess.VIEW,
        )


def test_child_definition_requires_expected_type() -> None:
    with pytest.raises(ValueError, match='requires an expected Glue type'):
        GlueAttributeDefinition(
            path='panel',
            source_name='panel',
            kind=GlueAttributeKind.CHILD,
            required_access=GlueAccess.VIEW,
        )


def test_non_editable_definition_rejects_setter() -> None:
    with pytest.raises(ValueError, match='Only editable value'):
        GlueAttributeDefinition(
            path='status',
            source_name='status',
            kind=GlueAttributeKind.VALUE,
            required_access=GlueAccess.VIEW,
            value_role=GlueValueRole.DERIVED_OUTPUT,
            setter=lambda owner, value: setattr(owner, 'status', value),
        )


def test_non_callable_definition_rejects_callable_target() -> None:
    with pytest.raises(ValueError, match='Non-callable attribute'):
        GlueAttributeDefinition(
            path='status',
            source_name='status',
            kind=GlueAttributeKind.VALUE,
            required_access=GlueAccess.VIEW,
            value_role=GlueValueRole.DERIVED_OUTPUT,
            callable_target=lambda owner: owner.status,
        )


def test_definition_rejects_empty_path_segments() -> None:
    with pytest.raises(ValueError, match='empty segment'):
        GlueAttributeDefinition(
            path='services..ping',
            source_name='ping',
            kind=GlueAttributeKind.CALLABLE,
            required_access=GlueAccess.VIEW,
        )


def test_definition_rejects_reserved_client_name() -> None:
    with pytest.raises(ValueError, match='reserved client name'):
        GlueAttributeDefinition(
            path='services.$fields.ping',
            source_name='ping',
            kind=GlueAttributeKind.CALLABLE,
            required_access=GlueAccess.VIEW,
        )


def test_definition_rejects_prototype_sensitive_client_name() -> None:
    with pytest.raises(ValueError, match='prototype-sensitive client name'):
        GlueAttributeDefinition(
            path='services.toString',
            source_name='toString',
            kind=GlueAttributeKind.CALLABLE,
            required_access=GlueAccess.VIEW,
        )


def test_bound_namespace_constructs_provider_per_access() -> None:
    owner = type('Owner', (), {'services': Glue.namespace(BaseConstructorLike)})()
    registry = GlueAttributeRegistry(
        GlueAttributeCollector.collect(type(owner))
    )
    bound = BoundGlueAttribute(
        definition=registry.get('services'),
        owner=owner,
    )

    first = bound.get()
    second = bound.get()

    assert isinstance(first, BaseConstructorLike)
    assert first is not second
    assert first.target is owner


def test_bound_namespace_resolves_nested_provider_at_access_time() -> None:
    class FactoryProvider:
        def __init__(self, target: object) -> None:
            self.target = target

        @Glue.attr
        def duplicate(self) -> object:
            return self.target.target

    class ServicesProvider:
        def __init__(self, target: object) -> None:
            self.target = target

        factory = Glue.namespace(FactoryProvider)

    class Owner:
        services = Glue.namespace(ServicesProvider)

    owner = Owner()
    registry = GlueAttributeRegistry(
        GlueAttributeCollector.collect(Owner)
    )
    attributes = {
        attribute.definition.path: attribute
        for attribute in registry.bind(owner)
    }

    duplicate = attributes['services.factory.duplicate'].get()

    assert duplicate() is owner
