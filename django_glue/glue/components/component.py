from __future__ import annotations

import inspect
import warnings
from functools import cache, cached_property
from typing import TYPE_CHECKING, Any, Callable, ClassVar

from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import render as render_template
from django.views.decorators.http import require_safe
from pydantic import ValidationError

from django_glue.access import GlueAccess
from django_glue.serialization import GlueSerializerError, glue_serializer_registry
from django_glue.exceptions import (
    GlueAccessError,
    GlueAuthorizationError,
    GlueComponentParameterError,
    GlueError,
    GlueRequestError,
    GlueRequestErrorCode,
)
from django_glue.glue.annotations import resolve_annotations
from django_glue.glue.attributes import GlueAttributeDeclaration
from django_glue.glue.attributes.attribute import GlueAttributeKind, GlueValueRole
from django_glue.glue.attributes.declaration import _MISSING
from django_glue.glue.base import BaseGlue
from django_glue.glue.components.naming import component_name
from django_glue.glue.components.registry import CAMEL_BOUNDARY, component_registry
from django_glue.glue.components.root import inject_component_root
from django_glue.glue.components.session import ComponentSession
from django_glue.glue.context import GlueContextManager
from django_glue.glue.event import RECEIVE_ATTRIBUTE, GlueEvent, declared_event_identities
from django_glue.glue.listener import GlueListener, ReceivedEvent, require_declared_events
from django_glue.glue.model_parameter import ModelParameter
from django_glue.glue.operation import GlueOperation, GlueOperationKind
from django_glue.glue.policy import GluePolicy
from django_glue.resolver.attribute_call.context import AttributeCallRequestContext
from django_glue.response import GlueResponse, GlueTemplateResponse

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from django.http import HttpRequest

    from django_glue.serialization import GlueSerializer
    from django_glue.glue.children import BoundGlueChild


class _DefaultFactory:
    def __repr__(self) -> str:
        return '<factory>'


VIEW_COMPONENT_CONTEXT_KEY = '_django_glue_view_component'
# The addresses of the children a re-render keeps rather than re-stamps (ADR 025).
MOUNTED_CHILDREN_CONTEXT_KEY = '_django_glue_mounted_children'


@cache
def _parameter_types(component_class: type[Component]) -> dict[str, Any]:
    annotations = resolve_annotations(component_class, component_class._declared_parameters())
    return {
        key: declaration.model_class if isinstance(declaration, ModelParameter) else annotations[key]
        for key, declaration in component_class._declared_parameters().items()
    }


@cache
def _parameter_serializers(component_class: type[Component]) -> dict[str, GlueSerializer]:
    """The serializer of each parameter that is a value; a model parameter signs its own key."""
    annotations = _parameter_types(component_class)
    return {
        key: glue_serializer_registry.resolve(annotations[key])
        for key, declaration in component_class._declared_parameters().items()
        if not isinstance(declaration, ModelParameter)
    }


@cache
def _post_init_keywords(component_class: type[Component]) -> tuple[frozenset[str], bool]:
    """
    The keyword names ``__post_init__`` takes beyond the request, and whether
    it takes any keyword through ``**kwargs``.
    """
    signature = inspect.signature(component_class.__post_init__)
    hook_parameters = list(signature.parameters.values())[2:]
    return (
        frozenset(
            parameter.name
            for parameter in hook_parameters
            if parameter.kind in (parameter.POSITIONAL_OR_KEYWORD, parameter.KEYWORD_ONLY)
        ),
        any(parameter.kind is parameter.VAR_KEYWORD for parameter in hook_parameters),
    )


@cache
def _reactions(component_class: type[Component]) -> dict[str, list[str]]:
    """The identities of the events a class re-renders on and listens for, as
    its static data publishes them (ADR 024, ADR 025); empty lists omitted."""
    reactions = {
        'rerender_on': sorted({event.identity for event in component_class.rerender_on}),
        'listeners': sorted({
            identity
            for listener in component_class._glue_listeners.values()
            for identity in listener.event_identities
        }),
    }
    return {key: identities for key, identities in reactions.items() if identities}


class Component(BaseGlue):
    namespace: ClassVar[str] = 'component'
    template: str | None = None
    view_template: str | None = None
    rerender_on: ClassVar[tuple[GlueEvent, ...]] = ()
    _glue_listeners: ClassVar[dict[str, GlueListener]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        declared = cls._declared_parameters()
        # Only the parameters' annotations: any other, such as a ClassVar typed with a
        # TYPE_CHECKING import, is never evaluated.
        annotations = resolve_annotations(cls, declared)
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
                inspect.Parameter('defer_render', keyword, default=False, annotation=bool),
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
        if 'rerender_on' in cls.__dict__ and cls.rerender_on:
            require_declared_events(cls.rerender_on, f'{cls.__name__}.rerender_on')
        cls._glue_listeners = {
            name: value
            for base in reversed(cls.__mro__)
            for name, value in base.__dict__.items()
            if isinstance(value, GlueListener)
        }
        if cls.template is not None:
            component_registry.register(cls)
        if 'get_view_kwargs' in cls.__dict__:
            message = (
                f'{cls.__name__}.get_view_kwargs() was removed and is never called. Derive '
                'request-dependent parameters and access in __post_init__() instead.'
            )
            raise TypeError(message)
        if 'get_context_data' in cls.__dict__:
            message = (
                f'{cls.__name__}.get_context_data() was removed and is never called. Read what '
                "the component's template shows from the component, and add page context to "
                'self.context_data in __post_init__().'
            )
            raise TypeError(message)
        if 'layout_template' in cls.__dict__:
            message = f'{cls.__name__}.layout_template was renamed to view_template.'
            raise TypeError(message)
        if 'mount' in cls.__dict__:
            warnings.warn(
                f'{cls.__name__}.mount() is deprecated and will be removed in a future '
                'version of django-glue. Rename it to __post_init__().',
                DeprecationWarning,
                # Past __init_subclass__ and ABCMeta.__new__ to the class statement.
                stacklevel=3,
            )

    @classmethod
    def _declared_parameters(cls) -> dict[str, GlueAttributeDeclaration]:
        return {
            key: value
            for base in reversed(cls.__mro__)
            for key, value in base.__dict__.items()
            if isinstance(value, GlueAttributeDeclaration) and value._parameter
        }

    def __init__(
        self,
        *,
        name: str | None = None,
        access: GlueAccess = GlueAccess.VIEW,
        defer_render: bool = False,
        **parameters: Any,
    ) -> None:
        declared = self._declared_parameters()
        accepted, accepts_any = _post_init_keywords(type(self))
        self._post_init_kwargs: dict[str, Any] = {
            key: parameters.pop(key) for key in parameters.keys() - declared.keys()
        }
        unknown = set() if accepts_any else self._post_init_kwargs.keys() - accepted
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
        self._ancestors: tuple[str, ...] = ()
        self._mounted_children: frozenset[str] = frozenset()
        self._access_ceiling: GlueAccess | None = None
        # Only the response that introduces a returned component reads it, so it is not signed.
        self._defer_render = defer_render
        # as_view() sets it before introducing the component; it is not signed (ADR 045).
        self._served_as_view = False
        self.context_data: dict[str, Any] = {}

        if not self.template:
            msg = f'{type(self).__name__} must declare a template path.'
            raise ValueError(msg)

        serializers = _parameter_serializers(type(self))
        for key, declaration in declared.items():
            if key in parameters:
                value = parameters[key]
            elif isinstance(declaration, ModelParameter):
                # Reading it would run the initializer before the other parameters are assigned.
                value = declaration.default
            else:
                value = getattr(self, key)
            if isinstance(value, BaseGlue):
                raise GlueComponentParameterError(f'Parameter {key!r} cannot be a Glue object.')
            if isinstance(declaration, ModelParameter):
                setattr(self, key, value)
                continue
            try:
                setattr(self, key, serializers[key].load(value))
            except GlueSerializerError as error:
                raise GlueComponentParameterError(
                    f'Invalid parameter {key!r} on {type(self).__name__}.'
                ) from error

    def _get_retained_state(self) -> dict[str, Any]:
        return {
            path: bound.wire_value()
            for path, bound in self._bound_attributes.items()
            if bound.attribute.kind is GlueAttributeKind.VALUE
            and (
                bound.attribute.value_role is GlueValueRole.EDITABLE_STATE
                or (
                    bound.attribute.value_role is GlueValueRole.RECONSTRUCTOR
                    and not bound.attribute.is_parameter
                )
            )
        }

    @property
    def served_as_view(self) -> bool:
        """
        Whether as_view() is serving this component on this request, from
        __post_init__() on. A component a tag or a callable introduces, or one
        rebuilt from its token for a later call, is not (ADR 045).
        """
        return self._served_as_view

    @property
    def lineage(self) -> tuple[str, ...]:
        """This component's address and its ancestors': the ancestry of a child it stamps or returns."""
        return (self.address, *self._ancestors)

    @property
    def identity(self) -> dict[str, Any]:
        serializers = _parameter_serializers(type(self))
        parameters = {
            key: (
                declaration.signed_value(self)
                if isinstance(declaration, ModelParameter)
                else serializers[key].dump(getattr(self, key))
            )
            for key, declaration in self._declared_parameters().items()
        }
        return {
            'component_id': f'{type(self).__module__}.{type(self).__qualname__}',
            'parameters': parameters,
            'ancestors': list(self._ancestors),
        }

    @cached_property
    def session(self) -> ComponentSession:
        if self.request is None:
            message = f"Cannot access the session of unbound component '{self.name}'."
            raise RuntimeError(message)

        def send_written_session_attribute(key: str) -> None:
            # A session attribute's value was re-derived by the write, so this
            # response carries it even when nothing re-renders the component.
            declaration = inspect.getattr_static(type(self), key, None)
            if isinstance(declaration, GlueAttributeDeclaration) and declaration._session:
                self._derived_paths.add(key)

        return ComponentSession(
            self.request.session,
            f'{type(self).__module__}.{type(self).__qualname__}',
            on_write=send_written_session_attribute,
        )

    @classmethod
    def _reconstruct_from_policy(cls, policy: GluePolicy) -> Component:
        component_class = component_registry.from_identifier(policy.identity['component_id'])
        component = component_class(
            name=policy.name,
            access=policy.access,
            **policy.identity['parameters'],
        )
        component._ancestors = tuple(policy.identity.get('ancestors', ()))
        for key, value in policy.state_snapshot.items():
            bound = component._bound_attributes.get(key)
            if bound is not None and bound.attribute.value_role is GlueValueRole.RECONSTRUCTOR:
                annotation = resolve_annotations(component_class, [key]).get(key)
                setattr(component, key, glue_serializer_registry.resolve(annotation).restore(value))
        return component

    @classmethod
    def event_declaring_classes(cls, policy: GluePolicy) -> tuple[type, ...]:
        return (component_registry.from_identifier(policy.identity['component_id']),)

    @classmethod
    def reacting_events(
        cls,
        policy: GluePolicy,
        source_policy: GluePolicy,
        identities: Iterable[str],
    ) -> list[str]:
        """Its ``rerender_on`` events, and its listeners' when a descendant emits them."""
        reactions = _reactions(component_registry.from_identifier(policy.identity['component_id']))
        reacting = set(reactions.get('rerender_on', ()))
        if policy.address in source_policy.identity.get('ancestors', ()):
            reacting.update(reactions.get('listeners', ()))
        return [identity for identity in identities if identity in reacting]

    def get_static_data(self) -> dict[str, Any]:
        """
        Adds the identities of the events this component re-renders on and
        listens for, which the client uses to route events (ADR 024, ADR 025):
        ``rerender_on`` page-wide, ``listeners`` to ancestors only.
        """
        static_data = super().get_static_data()
        static_data.update(_reactions(type(self)))
        for path, slot in static_data.get('children', {}).items():
            if self._bound_attributes[path].attribute.is_declared_child:
                slot['submits_with_owner'] = True
        return static_data

    def cap_access(self, ceiling: GlueAccess) -> None:
        self._access_ceiling = ceiling
        super().cap_access(ceiling)

    def introduce(self, request: HttpRequest) -> None:
        super().introduce(request)
        introduced_access = self.access
        self.mount()
        self.__post_init__(request, **self._post_init_kwargs)

        if self.access == introduced_access:
            return

        if self._access_ceiling is not None:
            super().cap_access(self._access_ceiling)
        operation = GlueOperation(
            kind=GlueOperationKind.INTRODUCE,
            attribute=None,
            required_access=self.access,
        )
        try:
            self._authorize(request, operation)
        except GlueAuthorizationError:
            self.request = None
            raise

    def mount(self) -> None:
        pass

    def __post_init__(self, request: HttpRequest) -> None:
        """
        Validate and set up the component when it first appears on a page.

        Runs once per introduction, after the parameters are assigned and the
        component is authorized for ``request`` and bound to it, and before its
        first policy token and HTML are produced. It does not run when a later
        action rebuilds the component from its token, so a value a later
        action reads must be assigned to a declared attribute.

        A subclass may add keyword parameters after ``request``. A value a URL
        capture, ``as_view()`` or the template tag passes under a name that is
        not a declared parameter is given to the matching keyword, and is
        neither signed nor kept after this call.

        Assigning ``self.access`` here sets the level the component is signed
        with. A changed level is capped at the level of the component whose
        callable returned this one, then authorized again.

        Values added to ``self.context_data`` here join the context of the
        view template around a component ``as_view()`` serves, such as its
        page title and breadcrumbs. The component's own template never sees
        them: it is drawn again after calls, from the token, so what it shows
        comes from the component, its attributes and properties.
        """

    def _run_call(
        self,
        call_context: AttributeCallRequestContext,
        invoke: Callable[[], Any],
        *,
        render_as_html: bool = False,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """
        Refuse a call that changed ``context_data``: the next render is built
        from the token, which does not carry it.

        Every child the call read with the user's changes applied answers in
        the same response, so what it derived from them (a form's errors)
        reaches the browser.
        """
        context_data = dict(self.context_data)
        entry, introduced = super()._run_call(call_context, invoke, render_as_html=render_as_html)

        if self.context_data != context_data:
            message = (
                f'{type(self).__name__}.{call_context.target_attribute_name}() changed '
                'context_data, which only __post_init__() may do: it is not kept for later '
                'renders. Read what the template shows from the component instead.'
            )
            raise RuntimeError(message)

        return entry, self._with_submitted_entries(introduced)

    def _with_submitted_entries(self, introduced: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        The entries of the children a request introduced, after those of every
        child it read with the user's changes applied, each address once.
        """
        submitted = [
            child_entry
            for child in self.__dict__.get('_submitted_children', {}).values()
            for child_entry in child._submission_entries()
        ]
        addresses = {child_entry['address'] for child_entry in submitted}
        return [
            *submitted,
            *(child_entry for child_entry in introduced if child_entry['address'] not in addresses),
        ]

    @classmethod
    def as_view(
        cls,
        *,
        view_template: str | None = None,
        access: GlueAccess = GlueAccess.VIEW,
        **parameters: Any,
    ) -> Callable[..., HttpResponse]:
        """
        Build a view that responds to a safe request with this component.

        URL captures and ``parameters`` construct the component. It is
        introduced, then rendered inside the view template (the argument,
        else the class's ``view_template``), or alone as a fragment when
        there is none. A denial at introduction responds 403, or with the
        response a view decorator on ``is_authorized()`` answered it with.
        """
        if parameters.get('defer_render'):
            raise GlueComponentParameterError(
                f'{cls.__name__}.as_view() renders its component, so it cannot take '
                'defer_render, which only defers the render of a component a callable returns.'
            )

        @require_safe
        def view(request: HttpRequest, **url_parameters: Any) -> HttpResponse:
            component = cls(access=access, **{**parameters, **url_parameters})
            component._served_as_view = True
            page_template = view_template if view_template is not None else component.view_template
            try:
                GlueContextManager(request).add_glue(component)
                if page_template is not None:
                    return render_template(
                        request,
                        page_template,
                        {
                            **component.context_data,
                            'component': component,
                            VIEW_COMPONENT_CONTEXT_KEY: component,
                        },
                    )
                return HttpResponse(component.render().html)
            except GlueAuthorizationError as error:
                if error.response is not None:
                    return error.response
                raise PermissionDenied from error

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
        longer match the component's state. A callable whose response
        redirects never re-renders (ADR 037). The render runs on a fresh
        instance built from the successor token rather than on ``self``, whose
        derived values (cached properties and the like) were computed before
        the call. That render's output is the authoritative HTML and computed
        data; the call's own result and effects stand.

        A refresh reads the children the browser submitted with it as a call
        does, and answers with each one it read (ADR 049).
        """
        self.__dict__['_call_context'] = call_context
        if call_context.target_attribute_name == RECEIVE_ATTRIBUTE:
            return self._receive(call_context)

        entry, introduced = super().process_attribute_call(call_context)
        if call_context.target_attribute_name is None:
            introduced = self._with_submitted_entries(introduced)
        if 'html' in entry:
            return entry, introduced

        # The browser is leaving the page, so nothing on it needs to match the component (ADR 037).
        if entry.get('effects', {}).get('redirect') is not None:
            return entry, introduced

        attribute_name = call_context.target_attribute_name
        if attribute_name is not None and 'policy_token' not in entry:
            attribute = self._bound_attributes[attribute_name].attribute
            if attribute.skip_rerender or attribute.expected_type is not None:
                return entry, introduced

        return self._rerendered(entry, introduced, call_context)

    def _bind_children(
        self,
        *,
        live_children: Mapping[str, str] | None = None,
        reintroduce: Iterable[str] = (),
    ) -> tuple[BoundGlueChild, ...]:
        """
        Binding a slot runs its initializer for a new child, which the binder
        introduces itself. A submitted child is an existing one, already bound,
        and the child the component's own reads built is never introduced, so
        both are set aside here (ADR 049).
        """
        call_context = self.__dict__.pop('_call_context', None)
        initialized = self.__dict__.pop('_initialized_children', None)
        try:
            return super()._bind_children(live_children=live_children, reintroduce=reintroduce)
        finally:
            if call_context is not None:
                self.__dict__['_call_context'] = call_context
            if initialized is not None:
                self.__dict__['_initialized_children'] = initialized

    def _submitted_child(self, path: str) -> BaseGlue | None:
        """
        The child at ``path`` as the browser submitted it with this call: rebuilt
        from its own signed token, with the user's unsaved changes applied. None
        when there is no call, or the browser sent nothing for the slot.

        The submission is checked here, when a call first reads the child, so a
        call that reads no child is unaffected by what was sent with it.
        """
        from django_glue.glue.registry import glue_class_registry  # noqa: PLC0415

        call_context = self.__dict__.get('_call_context')
        if call_context is None or path not in call_context.child_submissions:
            return None

        submitted = self.__dict__.setdefault('_submitted_children', {})
        if path in submitted:
            return submitted[path]

        submission = call_context.child_submissions[path]
        try:
            child_policy = GluePolicy.from_token(submission['policy_token'])
            child_policy.verify_request(call_context.request)
        except (GlueError, ValidationError, KeyError, TypeError) as error:
            raise GlueRequestError(
                code=GlueRequestErrorCode.INVALID_CHILD_SUBMISSION,
                message='A submitted child needs its own valid signed token.',
                details={'path': path},
            ) from error

        if (
            child_policy.address != call_context.target_glue_policy.children.get(path)
            or not child_policy.access.has_access(GlueAccess.ADD)
        ):
            raise GlueRequestError(
                code=GlueRequestErrorCode.INVALID_CHILD_SUBMISSION,
                message='The submitted token is not a writable child in this slot.',
                details={'path': path},
            )

        child_context = call_context.for_child_submission(
            path=path,
            child_policy=child_policy,
            updates=submission.get('updates', {}),
        )
        child = glue_class_registry.get_glue_class(
            child_policy.namespace,
        ).from_attribute_call_resolver_context(child_context)
        child._hydrate_submission(child_context, submission)
        submitted[path] = child
        return child

    def _receive(
        self,
        call_context: AttributeCallRequestContext,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Handle events the client delivered (ADR 024, ADR 025).

        ``rerender_on`` takes an event from any component on the page;
        listeners run only for an event from a descendant, because they can
        read ``event.source``. Every listener is authorized before any runs.
        The component re-renders once for the whole delivery when an event is
        in ``rerender_on``, or when a listener ran that does not skip it, or
        when a retained value changed.
        """
        rerender_identities = set(_reactions(type(self)).get('rerender_on', ()))
        deliveries: list[tuple[GlueListener, ReceivedEvent[Any]]] = []
        rerender = False
        for identity, event, from_descendant in self._admit_received_events(call_context):
            listeners = [
                listener
                for listener in self._glue_listeners.values()
                if identity in listener.event_identities
            ]
            if identity not in rerender_identities:
                if not listeners:
                    raise GlueRequestError(
                        code=GlueRequestErrorCode.INVALID_KWARGS,
                        message=f'{type(self).__name__} neither re-renders on nor listens for the delivered event.',
                        details={'event': identity},
                    )
                if not from_descendant:
                    raise GlueRequestError(
                        code=GlueRequestErrorCode.INVALID_KWARGS,
                        message='The event source is not a descendant of this component.',
                        details={'source': event.source_address},
                    )
            rerender = rerender or identity in rerender_identities
            if from_descendant:
                deliveries.extend((listener, event) for listener in listeners)

        policy = call_context.target_glue_policy
        for listener, _event in deliveries:
            if not policy.access.has_access(listener.required_access):
                raise GlueAccessError(
                    attribute=listener.name,
                    required_access=listener.required_access.value,
                    current_access=policy.access.value,
                )
            self._require_authorization(GlueOperation(
                kind=GlueOperationKind.CALL,
                attribute=listener.name,
                required_access=listener.required_access,
            ))

        def invoke() -> None:
            for listener, event in deliveries:
                listener.run(self, event)

        entry, introduced = self._run_call(call_context, invoke)
        rerender = rerender or any(not listener.skip_rerender for listener, _event in deliveries)
        if 'policy_token' not in entry and not rerender:
            return entry, introduced
        return self._rerendered(entry, introduced, call_context)

    def _admit_received_events(
        self,
        call_context: AttributeCallRequestContext,
    ) -> list[tuple[str, ReceivedEvent[Any], bool]]:
        """
        Verify each delivered event's source before any listener runs.

        The source token must be genuine and issued to this session and user,
        and the source must declare or inherit the event, on its own class or
        an attribute provider's (ADR 039). Any Glue object may be the source.
        Each event comes back with whether its source names this component
        among its signed ancestors, which only a component's token can. The
        detail stays untrusted.
        """
        from django_glue.glue.registry import glue_class_registry  # noqa: PLC0415

        kwargs = call_context.target_attribute_call_kwargs
        deliveries = kwargs.get('events')
        if set(kwargs) != {'events'} or not isinstance(deliveries, list) or not deliveries:
            raise GlueRequestError(
                code=GlueRequestErrorCode.INVALID_KWARGS,
                message=f'{RECEIVE_ATTRIBUTE} takes a non-empty "events" list.',
            )

        received: list[tuple[str, ReceivedEvent[Any], bool]] = []
        for delivery in deliveries:
            if (
                not isinstance(delivery, dict)
                or not isinstance(delivery.get('event'), str)
                or not isinstance(delivery.get('source_token'), str)
                or not isinstance(delivery.get('detail', {}), dict)
            ):
                raise GlueRequestError(
                    code=GlueRequestErrorCode.INVALID_KWARGS,
                    message='Each delivered event needs "event", "source_token", and an object "detail".',
                )
            source_policy = GluePolicy.from_token(delivery['source_token'])
            source_policy.verify_request(call_context.request)
            try:
                glue_class = glue_class_registry.get_glue_class(source_policy.namespace)
            except KeyError as error:
                raise GlueRequestError(
                    code=GlueRequestErrorCode.INVALID_KWARGS,
                    message='The event source is not a Glue object.',
                    details={'source': source_policy.address},
                ) from error
            declaring_classes = glue_class.event_declaring_classes(source_policy)
            source_class = declaring_classes[0]
            names_by_identity = {
                identity: name for name, identity in declared_event_identities(*declaring_classes).items()
            }
            if delivery['event'] not in names_by_identity:
                raise GlueRequestError(
                    code=GlueRequestErrorCode.INVALID_KWARGS,
                    message='The event source does not declare the delivered event.',
                    details={'source': source_policy.address, 'event': delivery['event']},
                )
            received.append((
                delivery['event'],
                ReceivedEvent(
                    name=names_by_identity[delivery['event']],
                    detail=delivery.get('detail', {}),
                    source_policy=source_policy,
                    source_class=source_class,
                    request=call_context.request,
                ),
                self.address in source_policy.identity.get('ancestors', ()),
            ))
        return received

    def _introduce_result(self, result: BaseGlue) -> None:
        if isinstance(result, Component):
            result._ancestors = self.lineage
        super()._introduce_result(result)

    def _result_entries(self) -> list[dict[str, Any]]:
        """
        A returned component arrives rendered (ADR 043): its entry carries the
        answer its first render() would get, so the client shows it without a
        second request. The render is the one a render() call runs, on a fresh
        instance from the token. A render Glue refuses, or one deferred with
        ``defer_render=True``, is left to that call.
        """
        entries = super()._result_entries()
        if self._defer_render:
            return entries

        render_context = AttributeCallRequestContext(
            request=self.request,
            target_glue_policy=self.policy,
            target_attribute_name='render',
            allow_uploaded_files=False,
        )
        try:
            fresh = type(self).from_attribute_call_resolver_context(render_context)
            render_entry, render_introduced = fresh.process_attribute_call(render_context)
        except GlueError:
            return entries

        entries[0]['answers'] = {'render': render_entry}
        return [*entries, *render_introduced]

    def _rerendered(
        self,
        entry: dict[str, Any],
        introduced: list[dict[str, Any]],
        call_context: AttributeCallRequestContext,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Replace ``entry``'s output with a render of the successor state (ADR 022).

        The render keeps the children the requesting entry reports mounted
        (ADR 025): this is the component re-rendering itself in place.

        It is given the call's child submissions, with each child the call read
        replaced by its successor, so it reads every child as the call left it
        (ADR 049). A child the call read has already answered, so the render's
        rebuilt copy of it does not answer again.
        """
        read_children = self.__dict__.get('_submitted_children', {})
        render_context = AttributeCallRequestContext(
            request=call_context.request,
            target_glue_policy=self.policy,
            target_attribute_name='render',
            child_submissions={
                **call_context.child_submissions,
                **{path: child._successor_submission() for path, child in read_children.items()},
            },
            allow_uploaded_files=call_context.allow_uploaded_files,
            suppressed_file_children=call_context.suppressed_file_children | frozenset(read_children),
        )
        fresh = type(self).from_attribute_call_resolver_context(render_context)
        fresh._mounted_children = frozenset(call_context.mounted)
        render_entry, render_introduced = fresh.process_attribute_call(render_context)

        entry['html'] = render_entry['html']
        entry.pop('computed_data', None)
        for key in ('policy_token', 'static_data', 'computed_data'):
            if key in render_entry:
                entry[key] = render_entry[key]
        answered = {child_entry['address'] for child_entry in introduced}
        return entry, [
            *introduced,
            *(
                child_entry
                for child_entry in render_introduced
                if child_entry['address'] not in answered
            ),
        ]

    @GlueAttributeDeclaration(required_access=GlueAccess.VIEW)
    def render(self) -> GlueResponse:
        if self.request is None:
            msg = f"Cannot render unbound component '{self.name}'."
            raise RuntimeError(msg)

        request: HttpRequest = self.request
        response = GlueTemplateResponse(
            request=request,
            template=self.template,
            # The component and nothing from context_data: this template is drawn again after
            # calls, from the token, so what it shows must come from the component.
            context={
                'component': self,
                MOUNTED_CHILDREN_CONTEXT_KEY: self._mounted_children,
            },
        )
        response.html = inject_component_root(
            response.html,
            self.address,
            self.template,
            [self.entry.model_dump(), *self._serialized_child_entries()],
        )
        return response
