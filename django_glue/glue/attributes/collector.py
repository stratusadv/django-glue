from __future__ import annotations

import inspect
from collections.abc import Iterable, Mapping
from dataclasses import replace
from functools import cache, partial
from typing import Any, TYPE_CHECKING

from django_glue.glue.attributes.definition import (
    GlueAttributeDefinition,
    GlueAttributeKind,
    GlueValueRole,
    _resolve_glue_result_annotation,
)

if TYPE_CHECKING:
    from django_glue.glue.attributes.declared import DeclaredAttributeOptions


_NAMESPACE_DEPTH_LIMIT = 20


class GlueAttributeCollector:
    @staticmethod
    @cache
    def collect(owner_type: type[Any]) -> tuple[GlueAttributeDefinition, ...]:
        return tuple(
            definition
            for source_name, static_attribute in inspect.getmembers_static(owner_type)
            if (options := GlueAttributeCollector._get_options(static_attribute)) is not None
            for definition in GlueAttributeCollector._compile_declaration(
                source_name=source_name,
                options=options,
                declaration=static_attribute,
            )
        )

    @staticmethod
    def collect_from_providers(
        attribute_providers: Iterable[Any],
    ) -> tuple[tuple[GlueAttributeDefinition, ...], dict[str, Any]]:
        definitions = []
        providers = {}
        for provider in attribute_providers:
            if provider is None:
                msg = 'Glue attribute providers cannot be None.'
                raise TypeError(msg)
            provider_definitions = GlueAttributeCollector.collect(type(provider))
            definitions.extend(provider_definitions)
            providers.update({
                definition.path: provider
                for definition in provider_definitions
            })
        return tuple(definitions), providers

    @staticmethod
    def collect_extra_attributes(
        attribute_groups: Iterable[tuple[Any, Mapping[str, Any]]],
    ) -> tuple[tuple[GlueAttributeDefinition, ...], dict[str, Any]]:
        definitions = []
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
                scoped_definitions = GlueAttributeCollector._compile_declaration(
                    source_name=path.split('.')[-1],
                    options=options,
                    path=path,
                    declaration=declaration,
                )
                definitions.extend(
                    GlueAttributeCollector._bind_scoped_declaration(
                        definition,
                        declaration,
                        path,
                    )
                    for definition in scoped_definitions
                )
                providers.update({
                    definition.path: provider
                    for definition in scoped_definitions
                })
        return tuple(definitions), providers

    @staticmethod
    def _bind_scoped_declaration(
        definition: GlueAttributeDefinition,
        declaration: Any,
        path: str,
    ) -> GlueAttributeDefinition:
        if definition.path != path or definition.kind == GlueAttributeKind.NAMESPACE:
            return definition
        has_descriptor = (
            getattr(declaration, 'target', None) is not None
            or getattr(declaration, '_property', None) is not None
        )
        if not has_descriptor:
            return definition
        getter = partial(
            GlueAttributeCollector._get_scoped_declaration,
            declaration=declaration,
        )
        if definition.kind == GlueAttributeKind.CALLABLE:
            return replace(
                definition,
                callable_target=getter,
            )
        setter = None
        if definition.value_role == GlueValueRole.EDITABLE_STATE:
            setter = partial(
                GlueAttributeCollector._set_scoped_declaration,
                declaration=declaration,
            )
        return replace(
            definition,
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
        options: DeclaredAttributeOptions,
        *,
        path: str | None = None,
        declaration: Any | None = None,
    ) -> tuple[GlueAttributeDefinition, ...]:
        path = path if path is not None else source_name
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
                GlueAttributeDefinition(
                    path=path,
                    source_name=source_name,
                    kind=GlueAttributeKind.CHILD,
                    required_access=options.required_access,
                    expected_type=options.expected_type,
                    is_nullable=options.is_nullable,
                ),
            )
        kind = (
            GlueAttributeKind.CALLABLE
            if options.is_callable
            else GlueAttributeKind.VALUE
        )
        allowed_arguments, injected_arguments = (
            GlueAttributeCollector._compile_callable_arguments(
                declaration,
                path,
            )
            if kind == GlueAttributeKind.CALLABLE
            else ((), ())
        )
        expected_type, is_nullable = (
            _resolve_glue_result_annotation(
                getattr(declaration, 'target', declaration),
            )
            if kind == GlueAttributeKind.CALLABLE
            else (None, False)
        )
        return (
            GlueAttributeDefinition(
                path=path,
                source_name=source_name,
                kind=kind,
                required_access=options.required_access,
                value_role=options.value_role,
                is_parameter=options.is_parameter,
                is_identity=options.is_identity,
                allowed_arguments=allowed_arguments,
                injected_arguments=injected_arguments,
                render_as_html=options.render_as_html,
                expected_type=expected_type,
                is_nullable=is_nullable,
            ),
        )

    @staticmethod
    def _compile_callable_arguments(
        declaration: Any | None,
        path: str,
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        target = getattr(declaration, 'target', declaration)
        if target is None or not callable(target):
            msg = f'Callable attribute {path!r} requires a callable target.'
            raise TypeError(msg)

        allowed_arguments = []
        injected_arguments = []
        for name, parameter in inspect.signature(inspect.unwrap(target)).parameters.items():
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

        return tuple(allowed_arguments), tuple(injected_arguments)

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
        options: DeclaredAttributeOptions,
        chain: frozenset[type[Any]],
        depth: int,
    ) -> tuple[GlueAttributeDefinition, ...]:
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

        definitions = [
            GlueAttributeDefinition(
                path=path,
                source_name=source_name,
                kind=GlueAttributeKind.NAMESPACE,
                required_access=options.required_access,
                provider_type=provider_type,
            ),
        ]
        next_chain = chain | {provider_type}
        for child_name, static_attribute in inspect.getmembers_static(provider_type):
            child_options = GlueAttributeCollector._get_options(static_attribute)
            if child_options is None:
                continue
            if child_options.is_namespace:
                definitions.extend(
                    GlueAttributeCollector._compile_namespace(
                        path=f'{path}.{child_name}',
                        source_name=child_name,
                        options=child_options,
                        chain=next_chain,
                        depth=depth + 1,
                    )
                )
            else:
                definitions.extend(
                    GlueAttributeCollector._compile_declaration(
                        source_name=child_name,
                        options=child_options,
                        path=f'{path}.{child_name}',
                        declaration=static_attribute,
                    )
                )
        return tuple(definitions)

    @staticmethod
    def _get_options(static_attribute: Any) -> DeclaredAttributeOptions | None:
        return getattr(
            static_attribute,
            '__glue_options__',
            None,
        )
