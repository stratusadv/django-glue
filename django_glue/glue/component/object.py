from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any, Self

from django.utils.html import format_html

from django_glue.access import GlueAccess
from django_glue.exceptions import (
    GlueComponentParameterError,
    GlueComponentRegistrationError,
)
from django_glue.glue.attributes.declared import DeclaredAttribute
from django_glue.glue.base import BaseGlue
from django_glue.glue.component.parameters import (
    coerce_parameter,
    resolve_parameter_annotations,
)
from django_glue.glue.component.registry import (
    TAG_NAME_PATTERN,
    derive_tag_name,
    glue_component_registry,
)
from django_glue.glue.loading import LoadingStrategy
from django_glue.response import GlueResponse, GlueTemplateResponse

if TYPE_CHECKING:
    from django_glue.glue.policy import GluePolicy


class Component(BaseGlue):
    """A Glue object that owns a template path and is stamped from a template.

    Components share one ``namespace`` so ``GlueClassRegistry`` stays a
    one-class-per-namespace map. Reconstruction is two-stage: the class
    registry resolves ``'component'`` to this base, and this base resolves
    ``identity['tag_name']`` through the component registry.

    See design/components/spec.md §§1-5.
    """

    namespace = 'component'

    template: str | None = None
    tag_name: str | None = None

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)

        # An intermediate base that declares no template is a shared ancestor,
        # not a stampable component, so it claims no public tag name.
        if cls.template is None:
            return

        tag_name = cls.__dict__.get('tag_name') or derive_tag_name(cls)

        if not TAG_NAME_PATTERN.match(tag_name):
            msg = (
                f"{cls.__name__} declares tag_name '{tag_name}', which is not "
                f'lowercase kebab-case segments (optionally dot-qualified).'
            )
            raise GlueComponentRegistrationError(msg)

        cls.tag_name = tag_name
        cls._parameter_names = cls._collect_parameter_names()
        cls._parameter_annotations = resolve_parameter_annotations(cls, cls._parameter_names)
        cls.__signature__ = cls._build_signature()

        glue_component_registry.register(cls, tag_name)

    def __init__(
        self,
        *,
        name: str | None = None,
        access: GlueAccess = GlueAccess.VIEW,
        loading_strategy: LoadingStrategy = LoadingStrategy.EAGER,
        **parameters: Any,
    ) -> None:
        if not self.template:
            msg = f'{type(self).__name__} must declare a template path.'
            raise GlueComponentRegistrationError(msg)

        super().__init__(
            name=name,
            access=access,
            loading_strategy=loading_strategy,
        )

        self._assign_parameters(parameters)

    @classmethod
    def _collect_parameter_names(cls) -> tuple[str, ...]:
        return tuple(
            attribute_name
            for attribute_name, attribute in inspect.getmembers_static(cls)
            if isinstance(attribute, DeclaredAttribute)
            and attribute.__glue_options__.is_parameter
        )

    @classmethod
    def _build_signature(cls) -> inspect.Signature:
        """Expose the declared parameters to inspect.signature and IDEs."""
        return inspect.Signature([
            inspect.Parameter(
                name,
                inspect.Parameter.KEYWORD_ONLY,
                annotation=cls._parameter_annotations[name],
            )
            for name in cls._parameter_names
        ])

    def _assign_parameters(self, parameters: dict[str, Any]) -> None:
        declared = set(self._parameter_names)
        supplied = set(parameters)

        undeclared = supplied - declared
        if undeclared:
            msg = (
                f'{type(self).__name__} received undeclared '
                f'parameter(s): {", ".join(sorted(undeclared))}. '
                f'Declared: {", ".join(self._parameter_names) or "none"}.'
            )
            raise GlueComponentParameterError(msg)

        missing = declared - supplied
        if missing:
            msg = (
                f'{type(self).__name__} requires '
                f'parameter(s): {", ".join(sorted(missing))}.'
            )
            raise GlueComponentParameterError(msg)

        for parameter_name, value in parameters.items():
            setattr(self, parameter_name, value)

    def get_identity(self) -> dict[str, Any]:
        """Sign the registered tag name alongside the declared parameters.

        The tag name is what the component registry resolves on reconstruction.
        It is never an import path, so an unregistered name fails closed.
        """
        return {
            'tag_name': self.tag_name,
            **super().get_identity(),
        }

    @classmethod
    def _reconstruct_from_policy(cls, policy: GluePolicy) -> Component:
        tag_name = policy.identity.get('tag_name')

        if not tag_name:
            msg = 'Component policy carries no tag_name and cannot be reconstructed.'
            raise GlueComponentRegistrationError(msg)

        component_class = glue_component_registry.get(tag_name)

        parameters = {
            parameter_name: coerce_parameter(
                parameter_name,
                policy.identity.get(parameter_name),
                component_class._parameter_annotations[parameter_name],
                component_class.__name__,
            )
            for parameter_name in component_class._parameter_names
        }

        component = component_class(
            name=policy.name,
            access=policy.access,
            **parameters,
        )
        component._is_reconstructed = True

        return component

    def mount(self) -> None:
        """Initial-introduction hook.

        Runs once, after parameters are assigned and the component is bound to
        the request, and before its first policy token and initial render. It
        does not run when reconstructing from a verified token, so it is the
        place to produce initial retained state — but a browser reload
        reintroduces the component, so it is not a once-per-lifetime hook.
        """

    def introduce(self, request: Any) -> Self:
        """Bind to the request and run the introduction hook."""
        self.request = request
        self.mount()
        return self

    @property
    def alpine_binding(self) -> str:
        """The ``x-data`` expression binding this component's proxy into scope.

        The proxy is bound under the name ``component``, matching what
        ``get_context_data()`` exposes to the template, so an attribute is
        spelled the same on both sides of the boundary: ``{{ component.total }}``
        renders it and ``x-text="component.total"`` binds it. A nested Alpine
        scope resolves the owning component through the ordinary scope chain
        rather than through a magic.

        ``Glue.<namespace>.<name>`` is read once, when ``x-data`` creates the
        scope. That registration is a getter that builds a *new* proxy on every
        access, so binding it here is what makes one proxy per scope fall out.
        """
        return format_html(
            '{{ component: Glue.{}.{} }}',
            self.namespace,
            self.name,
        )

    @property
    def root_attributes(self) -> str:
        """The attributes Glue injects into this component's rendered root.

        A component template is ordinary HTML and carries no Glue marker; these
        are added to whatever root element it rendered. ``data-glue`` is the
        morph target and makes the component identifiable in devtools.
        """
        return format_html(
            ' x-data="{}" data-glue="{}"',
            self.alpine_binding,
            self.name,
        )

    def get_context_data(self) -> dict[str, Any]:
        return {'component': self}

    @DeclaredAttribute(required_access=GlueAccess.VIEW, takes_client_state=False)
    def render(self) -> GlueResponse:
        """Render this component's template for mount or structural change.

        Steady-state updates flow through state and Alpine bindings instead;
        see design/components/spec.md §8.
        """
        if self.request is None:
            msg = f"Cannot render unbound component '{self.name}'."
            raise GlueComponentRegistrationError(msg)

        return GlueTemplateResponse(
            request=self.request,
            template=self.template,
            context=self.get_context_data(),
        )


Component._parameter_names: tuple[str, ...] = ()
Component._parameter_annotations: dict[str, Any] = {}
Component._is_reconstructed = False
