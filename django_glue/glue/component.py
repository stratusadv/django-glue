from __future__ import annotations

import inspect
import json
from typing import TYPE_CHECKING, Any, ClassVar, get_type_hints

from django_glue.access import GlueAccess
from django_glue.encoders import GlueResponseJSONEncoder
from django_glue.exceptions import GlueComponentParameterError
from django_glue.glue.attributes import DeclaredAttribute
from django_glue.glue.attributes.declared import _MISSING
from django_glue.glue.attributes.definition import GlueAttributeKind, GlueValueRole
from django_glue.glue.base import BaseGlue
from django_glue.glue.component_registry import CAMEL_BOUNDARY, component_registry
from django_glue.glue.component_root import inject_component_root
from django_glue.glue.policy import GluePolicy
from django_glue.response import GlueResponse, GlueTemplateResponse
from django_glue.serialization import GlueSerializerError, glue_serializer_registry

if TYPE_CHECKING:
    from django.http import HttpRequest


class _DefaultFactory:
    def __repr__(self) -> str:
        return '<factory>'


class Component(BaseGlue):
    namespace: ClassVar[str] = 'component'
    template: str | None = None
    tag_name: ClassVar[str | None] = None

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        annotations = get_type_hints(cls)
        declared = cls._declared_parameters()
        for key in declared:
            if key not in annotations:
                raise GlueComponentParameterError(
                    f'Parameter {key!r} on {cls.__name__} needs a type annotation.'
                )
        if cls.__init__ is Component.__init__:
            keyword = inspect.Parameter.KEYWORD_ONLY
            cls.__signature__ = inspect.Signature([
                inspect.Parameter('name', keyword, default=None, annotation=str | None),
                inspect.Parameter('template', keyword, default=None, annotation=str | None),
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
                        annotation=annotations[key],
                    )
                    for key, declaration in declared.items()
                ),
            ])
        if 'tag_name' not in cls.__dict__:
            cls.tag_name = CAMEL_BOUNDARY.sub('-', cls.__name__).lower()
        if cls.template is not None:
            component_registry.register(cls)

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
        template: str | None = None,
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
        super().__init__(name=name, access=access)

        resolved_template = template if template is not None else self.template
        if not resolved_template:
            msg = f'{type(self).__name__} must declare a template path.'
            raise ValueError(msg)

        self.template = resolved_template
        annotations = get_type_hints(type(self))
        for key in declared:
            value = parameters[key] if key in parameters else getattr(self, key)
            annotation = annotations[key]
            if isinstance(value, BaseGlue):
                raise GlueComponentParameterError(f'Parameter {key!r} cannot be a Glue object.')
            try:
                setattr(self, key, glue_serializer_registry.coerce(value, annotation))
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
        parameters = {key: getattr(self, key) for key in self._declared_parameters()}
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
