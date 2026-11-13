from __future__ import annotations

import inspect
from collections.abc import Callable, Iterable, Mapping
from contextlib import suppress
from dataclasses import replace
from functools import cache, partial
from typing import TYPE_CHECKING, Any, get_type_hints

from django_glue.glue.attributes.attribute import (
    GlueAttribute,
    GlueAttributeKind,
    GlueValueRole,
    _resolve_glue_result_annotation,
)
from django_glue.serialization import GlueSerializerError, glue_serializer_registry

if TYPE_CHECKING:
    from django_glue.serialization import GlueSerializer
    from django_glue.glue.attributes.declaration import GlueAttributeDeclarationOptions


_NAMESPACE_DEPTH_LIMIT = 20


class GlueAttributeCollector:
    @staticmethod
    @cache
    def collect(owner_type: type[Any]) -> tuple[GlueAttribute, ...]:
        value_types: dict[str, Any] = {}
        with suppress(NameError, TypeError):
            value_types = get_type_hints(owner_type)
        return tuple(
            attribute
            for source_name, static_attribute in inspect.getmembers_static(owner_type)
            if (options := GlueAttributeCollector._get_options(static_attribute)) is not None
            for attribute in GlueAttributeCollector._compile_declaration(
                source_name=source_name,
                options=options,
                declaration=static_attribute,
                value_type=value_types.get(source_name),
            )
        )

    @staticmethod
    def collect_from_providers(
        attribute_providers: Iterable[Any],
    ) -> tuple[tuple[GlueAttribute, ...], dict[str, Any]]:
        attributes = []
        providers = {}
        for provider in attribute_providers:
            if provider is None:
                msg = 'Glue attribute providers cannot be None.'
                raise TypeError(msg)
            provider_attributes = GlueAttributeCollector.collect(type(provider))
            attributes.extend(provider_attributes)
            providers.update({
                attribute.path: provider
                for attribute in provider_attributes
            })
        return tuple(attributes), providers

    @staticmethod
    def collect_extra_attributes(
        attribute_groups: Iterable[tuple[Any, Mapping[str, Any]]],
    ) -> tuple[tuple[GlueAttribute, ...], dict[str, Any]]:
        attributes = []
        providers = {}
        for provider, declarations in attribute_groups:
            if provider is None:
                msg = 'Glue attribute providers cannot be None.'
                raise TypeError(msg)
            if not isinstance(declarations, Mapping):
                msg = 'Glue attribute provider declarations must be a mapping.'
                raise TypeError(msg)
            for path, declaration in declarations.items():
                options = GlueAttributeCollector._get_options(declaration)
                if options is None:
                    msg = f'Glue attribute declaration {path!r} must use a Glue declaration.'
                    raise TypeError(msg)
                scoped_attributes = GlueAttributeCollector._compile_declaration(
                    source_name=path.split('.')[-1],
                    options=options,
                    path=path,
                    declaration=declaration,
                )
                attributes.extend(
                    GlueAttributeCollector._bind_scoped_declaration(
                        attribute,
                        declaration,
                        path,
                    )
                    for attribute in scoped_attributes
                )
                providers.update({
                    attribute.path: provider
                    for attribute in scoped_attributes
                })
        return tuple(attributes), providers

    @staticmethod
    def _bind_scoped_declaration(
        attribute: GlueAttribute,
        declaration: Any,
        path: str,
    ) -> GlueAttribute:
        if attribute.path != path or attribute.kind == GlueAttributeKind.NAMESPACE:
            return attribute
        has_descriptor = (
            getattr(declaration, 'target', None) is not None
            or getattr(declaration, '_property', None) is not None
        )
        if not has_descriptor:
            return attribute
        getter = partial(
            GlueAttributeCollector._get_scoped_declaration,
            declaration=declaration,
        )
        if attribute.kind == GlueAttributeKind.CALLABLE:
            return replace(
                attribute,
                callable_target=getter,
            )
        setter = None
        if attribute.value_role == GlueValueRole.EDITABLE_STATE:
            setter = partial(
                GlueAttributeCollector._set_scoped_declaration,
                declaration=declaration,
            )
        return replace(
            attribute,
            getter=getter,
            setter=setter,
        )

    @staticmethod
    def _get_scoped_declaration(
        provider: Any,
        *,
        declaration: Any,
    ) -> Any:
        return declaration.__get__(provider, type(provider))

    @staticmethod
    def _set_scoped_declaration(
        provider: Any,
        value: Any,
        *,
        declaration: Any,
    ) -> None:
        declaration.__set__(provider, value)

    @staticmethod
    def _compile_declaration(
        source_name: str,
        options: GlueAttributeDeclarationOptions,
        *,
        path: str | None = None,
        declaration: Any | None = None,
        value_type: Any | None = None,
    ) -> tuple[GlueAttribute, ...]:
        path = path if path is not None else source_name
        if options.value_type is not None:
            value_type = options.value_type
        if options.is_namespace:
            return GlueAttributeCollector._compile_namespace(
                path=path,
                source_name=source_name,
                options=options,
                chain=frozenset(),
                depth=0,
            )
        if options.expected_type is not None:
            return (
                GlueAttribute(
                    path=path,
                    source_name=source_name,
                    kind=GlueAttributeKind.CHILD,
                    required_access=options.required_access,
                    expected_type=options.expected_type,
                    is_nullable=options.is_nullable,
                    is_declared_child=options.is_declared_child,
                ),
            )
        kind = (
            GlueAttributeKind.CALLABLE
            if options.is_callable
            else GlueAttributeKind.VALUE
        )
        allowed_arguments, injected_arguments, argument_types = (
            GlueAttributeCollector._compile_callable_arguments(
                declaration,
                path,
            )
            if kind == GlueAttributeKind.CALLABLE
            else ((), (), {})
        )
        expected_type, is_nullable = (
            _resolve_glue_result_annotation(
                getattr(declaration, 'target', declaration),
            )
            if kind == GlueAttributeKind.CALLABLE
            else (None, False)
        )
        serializer = None
        if kind == GlueAttributeKind.VALUE and value_type is not None:
            try:
                serializer = glue_serializer_registry.resolve(value_type)
            except GlueSerializerError as error:
                msg = f'Value attribute {path!r} cannot hold its declared type: {error}'
                raise TypeError(msg) from error
        return (
            GlueAttribute(
                path=path,
                source_name=source_name,
                kind=kind,
                required_access=options.required_access,
                value_role=options.value_role,
                serializer=serializer,
                is_parameter=options.is_parameter,
                allowed_arguments=allowed_arguments,
                injected_arguments=injected_arguments,
                argument_types=argument_types,
                render_as_html=options.render_as_html,
                skip_rerender=options.skip_rerender,
                expected_type=expected_type,
                is_nullable=is_nullable,
            ),
        )

    @staticmethod
    def _compile_callable_arguments(
        declaration: Any | None,
        path: str,
    ) -> tuple[tuple[str, ...], tuple[str, ...], dict[str, GlueSerializer]]:
        target = getattr(declaration, 'target', declaration)
        if target is None or not callable(target):
            msg = f'Callable attribute {path!r} requires a callable target.'
            raise TypeError(msg)

        allowed_arguments = []
        injected_arguments = []
        argument_types = {}
        unwrapped = inspect.unwrap(target)
        for name, parameter in inspect.signature(unwrapped).parameters.items():
            if name == 'self' or parameter.kind in {
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            }:
                continue
            if parameter.kind == inspect.Parameter.POSITIONAL_ONLY:
                msg = (
                    f'Callable attribute {path!r} cannot expose positional-only '
                    f'argument {name!r}.'
                )
                raise TypeError(msg)

            annotation = parameter.annotation
            is_request = GlueAttributeCollector._is_request_annotation(annotation)
            if name == 'request':
                if annotation is not inspect.Parameter.empty and not is_request:
                    msg = (
                        f'Callable attribute {path!r} reserves argument '
                        f"'request' for HttpRequest injection."
                    )
                    raise TypeError(msg)
                injected_arguments.append(name)
            elif is_request:
                injected_arguments.append(name)
            else:
                allowed_arguments.append(name)
                if annotation is not inspect.Parameter.empty:
                    argument_types[name] = GlueAttributeCollector._resolve_argument_type(
                        unwrapped,
                        path,
                        name,
                        annotation,
                    )

        return tuple(allowed_arguments), tuple(injected_arguments), argument_types

    @staticmethod
    def _resolve_argument_type(
        target: Callable[..., Any],
        path: str,
        name: str,
        annotation: Any,
    ) -> GlueSerializer:
        """
        The serializer of one client-supplied argument. Its annotation is
        resolved on its own so an injected argument's type-checking-only import
        cannot block it, and evaluated rather than read through get_type_hints
        so Annotated metadata survives (ADR 038).
        """
        if isinstance(annotation, str):
            try:
                annotation = eval(annotation, dict(getattr(target, '__globals__', {})))  # noqa: S307
            except (AttributeError, NameError, SyntaxError, TypeError) as error:
                msg = (
                    f'Callable attribute {path!r} cannot resolve the annotation of '
                    f'argument {name!r}: {error}. Import its type at runtime.'
                )
                raise TypeError(msg) from error
        try:
            serializer = glue_serializer_registry.resolve(annotation)
            serializer.check()
        except GlueSerializerError as error:
            msg = f'Callable attribute {path!r} cannot serialize argument {name!r}: {error}'
            raise TypeError(msg) from error
        return serializer

    @staticmethod
    def _is_request_annotation(annotation: Any) -> bool:
        if isinstance(annotation, str):
            return annotation.strip("'\"").split('.')[-1] in {
                'HttpRequest',
                'WSGIRequest',
            }
        if not isinstance(annotation, type):
            return False
        return any(
            base.__name__ == 'HttpRequest'
            and base.__module__.startswith('django.http')
            for base in annotation.__mro__
        )

    @staticmethod
    def _compile_namespace(
        path: str,
        source_name: str,
        options: GlueAttributeDeclarationOptions,
        chain: frozenset[type[Any]],
        depth: int,
    ) -> tuple[GlueAttribute, ...]:
        provider_type = options.provider_type
        if provider_type is None:
            msg = f'Namespace attribute {path!r} requires a provider type.'
            raise ValueError(msg)
        if provider_type in chain:
            msg = f'Namespace provider graph cycles through {provider_type.__name__!r}.'
            raise ValueError(msg)
        if depth > _NAMESPACE_DEPTH_LIMIT:
            msg = f'Namespace provider graph exceeds depth limit at {path!r}.'
            raise ValueError(msg)

        attributes = [
            GlueAttribute(
                path=path,
                source_name=source_name,
                kind=GlueAttributeKind.NAMESPACE,
                required_access=options.required_access,
                provider_type=provider_type,
            ),
        ]
        value_types: dict[str, Any] = {}
        with suppress(NameError, TypeError):
            value_types = get_type_hints(provider_type)
        next_chain = chain | {provider_type}
        for child_name, static_attribute in inspect.getmembers_static(provider_type):
            child_options = GlueAttributeCollector._get_options(static_attribute)
            if child_options is None:
                continue
            if child_options.is_namespace:
                attributes.extend(
                    GlueAttributeCollector._compile_namespace(
                        path=f'{path}.{child_name}',
                        source_name=child_name,
                        options=child_options,
                        chain=next_chain,
                        depth=depth + 1,
                    )
                )
            else:
                attributes.extend(
                    GlueAttributeCollector._compile_declaration(
                        source_name=child_name,
                        options=child_options,
                        path=f'{path}.{child_name}',
                        declaration=static_attribute,
                        value_type=value_types.get(child_name),
                    )
                )
        return tuple(attributes)

    @staticmethod
    def _get_options(static_attribute: Any) -> GlueAttributeDeclarationOptions | None:
        return getattr(
            static_attribute,
            '__glue_options__',
            None,
        )
