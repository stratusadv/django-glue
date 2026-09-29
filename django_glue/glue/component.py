from __future__ import annotations

import inspect
import json
import warnings
from functools import cache
from typing import TYPE_CHECKING, Any, Callable, ClassVar, get_type_hints

from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import render as render_template
from django.views.decorators.http import require_safe

from django_glue.access import GlueAccess
from django_glue.encoders import GlueResponseJSONEncoder
from django_glue.exceptions import GlueAuthorizationError, GlueComponentParameterError
from django_glue.glue.attributes import DeclaredAttribute
from django_glue.glue.attributes.declared import _MISSING
from django_glue.glue.attributes.definition import GlueAttributeKind, GlueValueRole
from django_glue.glue.base import BaseGlue
from django_glue.glue.component_registry import CAMEL_BOUNDARY, component_registry
from django_glue.glue.component_naming import component_name
from django_glue.glue.component_root import inject_component_root
from django_glue.glue.context import GlueContextManager
from django_glue.glue.model_parameter import ModelParameter
from django_glue.glue.policy import GluePolicy
from django_glue.resolver.attribute_call.context import AttributeCallRequestContext
from django_glue.response import GlueResponse, GlueTemplateResponse
from django_glue.serialization import GlueSerializerError, glue_serializer_registry

if TYPE_CHECKING:
    from django.http import HttpRequest


class _DefaultFactory:
    def __repr__(self) -> str:
        return '<factory>'


VIEW_COMPONENT_CONTEXT_KEY = '_django_glue_view_component'


@cache
def _parameter_types(component_class: type[Component]) -> dict[str, Any]:
    annotations = get_type_hints(component_class)
    return {
        key: declaration.model_class if isinstance(declaration, ModelParameter) else annotations[key]
        for key, declaration in component_class._declared_parameters().items()
    }


class Component(BaseGlue):
    namespace: ClassVar[str] = 'component'
    template: str | None = None
    layout_template: str | None = None

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        annotations = get_type_hints(cls)
        declared = cls._declared_parameters()
        for key, declaration in declared.items():
            if isinstance(declaration, ModelParameter):
                declaration.validate_declaration()
            elif key not in annotations:
                raise GlueComponentParameterError(
                    f'Parameter {key!r} on {cls.__name__} needs a type annotation.'
                )
        parameter_types = _parameter_types(cls)

        if cls.__init__ is Component.__init__:
            keyword = inspect.Parameter.KEYWORD_ONLY
            cls.__signature__ = inspect.Signature([
                inspect.Parameter('name', keyword, default=None, annotation=str | None),
                inspect.Parameter('access', keyword, default=GlueAccess.VIEW, annotation=GlueAccess),
                *(
                    inspect.Parameter(
                        key,
                        keyword,
                        default=(
                            declaration.default
                            if declaration.default is not _MISSING
                            else _DefaultFactory()
                            if declaration.default_factory is not _MISSING
                            else inspect.Parameter.empty
                        ),
                        annotation=parameter_types[key],
                    )
                    for key, declaration in declared.items()
                ),
            ])
        if cls.template is not None:
            component_registry.register(cls)
        if 'get_view_kwargs' in cls.__dict__:
            warnings.warn(
                f'{cls.__name__}.get_view_kwargs() is deprecated and will be removed in '
                'django-glue 1.2.0. Construct the component in a view function and return '
                'component.as_page(request) instead.',
                DeprecationWarning,
                stacklevel=2,
            )

    @classmethod
    def _declared_parameters(cls) -> dict[str, DeclaredAttribute]:
        return {
            key: value
            for base in reversed(cls.__mro__)
            for key, value in base.__dict__.items()
            if isinstance(value, DeclaredAttribute) and value._parameter
        }

    def __init__(
        self,
        *,
        name: str | None = None,
        access: GlueAccess = GlueAccess.VIEW,
        **parameters: Any,
    ) -> None:
        declared = self._declared_parameters()
        unknown = parameters.keys() - declared.keys()
        if unknown:
            raise GlueComponentParameterError(
                f'Unknown parameters for {type(self).__name__}: {sorted(unknown)}'
            )
        missing = [
            key for key, declaration in declared.items()
            if key not in parameters
            and declaration.default is _MISSING
            and declaration.default_factory is _MISSING
        ]
        if missing:
            raise GlueComponentParameterError(
                f'Missing parameters for {type(self).__name__}: {missing}'
            )
        if name is None:
            stem = type(self).__name__.removesuffix('Component') or type(self).__name__
            name = component_name('', CAMEL_BOUNDARY.sub('_', stem).lower(), None)
        super().__init__(name=name, access=access)

        if not self.template:
            msg = f'{type(self).__name__} must declare a template path.'
            raise ValueError(msg)

        parameter_types = _parameter_types(type(self))
        for key, declaration in declared.items():
            value = parameters[key] if key in parameters else getattr(self, key)
            if isinstance(value, BaseGlue):
                raise GlueComponentParameterError(f'Parameter {key!r} cannot be a Glue object.')
            if isinstance(declaration, ModelParameter):
                setattr(self, key, value)
                continue
            try:
                setattr(self, key, glue_serializer_registry.coerce(value, parameter_types[key]))
            except GlueSerializerError as error:
                raise GlueComponentParameterError(
                    f'Invalid parameter {key!r} on {type(self).__name__}.'
                ) from error

    def _retained_state(self) -> dict[str, Any]:
        return {
            path: attribute.get()
            for path, attribute in self._bound_attributes.items()
            if attribute.definition.kind is GlueAttributeKind.VALUE
            and (
                attribute.definition.value_role is GlueValueRole.EDITABLE_STATE
                or (
                    attribute.definition.value_role is GlueValueRole.RECONSTRUCTOR
                    and not attribute.definition.is_parameter
                )
            )
        }

    @property
    def identity(self) -> dict[str, Any]:
        parameter_types = _parameter_types(type(self))
        parameters = {
            key: (
                declaration.signed_value(self)
                if isinstance(declaration, ModelParameter)
                else glue_serializer_registry.encode(getattr(self, key), parameter_types[key])
            )
            for key, declaration in self._declared_parameters().items()
        }
        return {
            'component_id': f'{type(self).__module__}.{type(self).__qualname__}',
            'parameters': json.loads(json.dumps(parameters, cls=GlueResponseJSONEncoder)),
        }

    @classmethod
    def _reconstruct_from_policy(cls, policy: GluePolicy) -> Component:
        component_class = component_registry.from_identifier(policy.identity['component_id'])
        component = component_class(
            name=policy.name,
            access=policy.access,
            **policy.identity['parameters'],
        )
        for key, value in policy.state_snapshot.items():
            attribute = component._bound_attributes.get(key)
            if attribute is not None and attribute.definition.value_role is GlueValueRole.RECONSTRUCTOR:
                annotation = get_type_hints(component_class).get(key)
                setattr(component, key, glue_serializer_registry.decode(value, annotation))
        return component

    def introduce(self, request: HttpRequest) -> None:
        super().introduce(request)
        self.mount()

    def mount(self) -> None:
        pass

    def get_context_data(self) -> dict[str, Any]:
        return {'component': self}

    @classmethod
    def get_view_kwargs(cls, request: HttpRequest, **url_kwargs: Any) -> dict[str, Any]:
        """Deprecated (ADR 023): construct the component in a view and call `as_page()`."""
        _ = request
        return url_kwargs

    def as_page(self, request: HttpRequest, *, layout_template: str | None = None) -> HttpResponse:
        """Respond to ``request`` with this component (ADR 023).

        The component is introduced and mounted, then rendered inside the layout
        template (the argument, else the class's ``layout_template``), or alone as
        a fragment when there is none. A denial at introduction responds 403.
        """
        layout = layout_template if layout_template is not None else self.layout_template
        try:
            GlueContextManager(request).add_glue(self)
            if layout is not None:
                return render_template(
                    request,
                    layout,
                    {
                        **self.get_context_data(),
                        VIEW_COMPONENT_CONTEXT_KEY: self,
                    },
                )
            return HttpResponse(self.render().html)
        except GlueAuthorizationError as error:
            raise PermissionDenied from error

    @classmethod
    def as_view(
        cls,
        *,
        layout_template: str | None = None,
        access: GlueAccess = GlueAccess.VIEW,
        **parameters: Any,
    ) -> Callable[..., HttpResponse]:
        @require_safe
        def view(request: HttpRequest, **url_parameters: Any) -> HttpResponse:
            view_kwargs = cls.get_view_kwargs(
                request,
                **{**parameters, **url_parameters},
            )
            component = cls(access=view_kwargs.pop('access', access), **view_kwargs)
            return component.as_page(request, layout_template=layout_template)

        return view

    def process_attribute_call(
        self,
        call_context: AttributeCallRequestContext,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Run the call and re-render the component in the same response (ADR 022).

        A refresh always re-renders. A callable re-renders unless its declared
        result is a Glue object, which hands the interaction to that object, or
        it declares ``skip_rerender=True``; either exception is overridden when
        the callable changed a retained value, because the markup would no
        longer match the component's state. The render runs on a fresh
        instance built from the successor token rather than on ``self``, whose
        derived values (cached properties and the like) were computed before
        the call. That render's output is the authoritative HTML and computed
        data; the call's own result and effects stand.
        """
        entry, introduced = super().process_attribute_call(call_context)
        if 'html' in entry:
            return entry, introduced

        attribute_name = call_context.target_attribute_name
        if attribute_name is not None and 'policy_token' not in entry:
            definition = self._bound_attributes[attribute_name].definition
            if definition.skip_rerender or definition.expected_type is not None:
                return entry, introduced

        render_context = AttributeCallRequestContext(
            request=call_context.request,
            target_glue_policy=self.policy,
            target_attribute_name='render',
        )
        fresh = type(self).from_attribute_call_resolver_context(render_context)
        render_entry, render_introduced = fresh.process_attribute_call(render_context)

        entry['html'] = render_entry['html']
        entry.pop('computed_data', None)
        for key in ('policy_token', 'static_data', 'computed_data'):
            if key in render_entry:
                entry[key] = render_entry[key]
        return entry, [*introduced, *render_introduced]

    @DeclaredAttribute(required_access=GlueAccess.VIEW)
    def render(self) -> GlueResponse:
        if self.request is None:
            msg = f"Cannot render unbound component '{self.name}'."
            raise RuntimeError(msg)

        request: HttpRequest = self.request
        response = GlueTemplateResponse(
            request=request,
            template=self.template,
            context=self.get_context_data(),
        )
        response.html = inject_component_root(
            response.html,
            self.address,
            self.template,
            [self.entry.model_dump(), *self._serialized_child_entries()],
        )
        return response
