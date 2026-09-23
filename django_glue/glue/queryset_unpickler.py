from __future__ import annotations

import base64
import importlib
import io
import pickle
from functools import lru_cache
from typing import Any, ClassVar

from django.apps import apps
from django.db.models import QuerySet

from django_glue.conf import settings as glue_settings


class QuerySetUnpickler(pickle.Unpickler):
    """Allowlisting unpickler for signed queryset continuations.

    ``find_class`` admits only the ORM, expression, field, and standard value
    types a serialized ``Query`` can legitimately contain, and raises on
    anything else (state-model.md §6). This is defence in depth behind the
    policy signature: the signature is what makes the payload trustworthy, and
    the allowlist is what limits the damage when the signature is not.

    Allowed by default:

    - Django's own ORM namespace (``django.db.models`` and its submodules):
      fields, lookups, expressions, aggregates, functions, ``query_utils``,
      ``sql.query``/``sql.where``/``sql.datastructures``, and so on.
    - model classes in the Django app registry -- the only models the server
      can issue querysets over.

    The allowlist is a published, versioned part of the contract. A project
    with a custom lookup or expression admits it deliberately with
    :meth:`register` rather than discovering an opaque failure.
    """

    VERSION = 1

    _django_orm_module = 'django.db.models'
    # Glue's own continuation-carrier classes. The signed continuation stores
    # choice-source configuration as an attribute on the serialized Query
    # (state-model.md: "The same path carries choice-source continuations"), so
    # its carrier class is published here, exactly like the framework types.
    _glue_continuation_classes: ClassVar[frozenset[str]] = frozenset({
        'django_glue.glue.options.django.choices.QuerySetChoiceOptions',
    })
    _registered_qualified_names: ClassVar[set[str]] = set()

    @classmethod
    def register(cls, qualified_name: str) -> None:
        """Admit a project type (e.g. a custom lookup or expression).

        ``qualified_name`` is the fully qualified class name, such as
        ``'myapp.lookups.MyLookup'``.
        """
        cls._registered_qualified_names.add(qualified_name)

    def find_class(self, module: str, name: str) -> Any:
        qualified_name = f'{module}.{name}'
        if self._is_allowed(qualified_name):
            return super().find_class(module, name)
        msg = (
            f'Refusing to unpickle {qualified_name!r}: outside the queryset '
            f'allowlist (QuerySetUnpickler v{self.VERSION}).'
        )
        raise pickle.UnpicklingError(msg)

    def _is_allowed(self, qualified_name: str) -> bool:
        if qualified_name in type(self)._registered_qualified_names:
            return True
        if qualified_name in type(self)._glue_continuation_classes:
            return True
        module, _separator, _name = qualified_name.rpartition('.')
        if module == self._django_orm_module or module.startswith(
            f'{self._django_orm_module}.'
        ):
            return True
        return qualified_name in self._known_model_names()

    @staticmethod
    @lru_cache(maxsize=1)
    def _known_model_names() -> frozenset[str]:
        return frozenset(
            f'{model.__module__}.{model.__name__}'
            for model in apps.get_models()
        )


def model_class_path(model: type[Any]) -> str:
    return f'{model.__module__}.{model.__name__}'


def pickle_query(queryset: QuerySet) -> str:
    """Encode a queryset's ``Query`` as a signed continuation, refusing one
    larger than the continuation bound it would later be rejected by."""
    encoded = base64.b64encode(pickle.dumps(queryset.query)).decode('ascii')
    if len(encoded) > glue_settings.DJANGO_GLUE_MAX_QUERY_ENCODED_BYTES:
        msg = (
            f'The {model_class_path(queryset.model)} queryset encodes to {len(encoded)} bytes, '
            'over DJANGO_GLUE_MAX_QUERY_ENCODED_BYTES.'
        )
        raise ValueError(msg)
    return encoded


def unpickle_query(encoded: str, expected_model_path: str) -> Any:
    """Base64-decode and unpickle a signed queryset continuation.

    Used by every queryset deserialization route (the queryset continuation
    and ``choices=`` sources) so both travel through the same size bound and
    allowlisting unpickler (state-model.md: "The same path carries
    choice-source continuations"). The encoded size is checked before
    decoding, and the query's model must match the signed identifier before
    the query is used.
    """
    if len(encoded) > glue_settings.DJANGO_GLUE_MAX_QUERY_ENCODED_BYTES:
        msg = 'Queryset continuation exceeds DJANGO_GLUE_MAX_QUERY_ENCODED_BYTES.'
        raise pickle.UnpicklingError(msg)
    query = QuerySetUnpickler(io.BytesIO(base64.b64decode(encoded))).load()
    if model_class_path(query.model) != expected_model_path:
        msg = f'Queryset continuation model does not match the signed {expected_model_path!r}.'
        raise pickle.UnpicklingError(msg)
    return query


def _queryset_class_path(queryset: QuerySet) -> str:
    """The signed identity entry naming the introducing queryset's class.

    A string, never a pickled object: reconstruction resolves the name and
    validates the result rather than trusting an opaque path. Used on both
    the queryset continuation and ``choices=`` sources, so either reconstructs
    through the queryset that produced it, never the default manager
    (roadmap: "reconstruct through the introducing queryset rather than the
    default manager either way"; scoped-policy.md: "Reconstruct the base
    queryset ... never the default manager").
    """
    return f'{type(queryset).__module__}.{type(queryset).__qualname__}'


def _resolve_queryset_class(queryset_class_path: str | None) -> type[QuerySet]:
    """Resolve a signed class path to the introducing queryset's class.

    The identity is server-signed, so importing the named module is the server
    referencing its own class. The resolved target must be a ``QuerySet``
    subclass; anything unresolvable or non-QuerySet fails loudly rather than
    silently degrading to the default manager.
    """
    if queryset_class_path is None:
        return QuerySet
    module_name, separator, qualname = queryset_class_path.rpartition('.')
    if not separator:
        msg = f'Queryset class path {queryset_class_path!r} is not a qualified name.'
        raise ValueError(msg)
    try:
        owner = importlib.import_module(module_name)
    except ImportError as error:
        msg = f'Cannot resolve queryset class {queryset_class_path!r}: {error}'
        raise ValueError(msg) from error
    for segment in qualname.split('.'):
        try:
            owner = getattr(owner, segment)
        except AttributeError as error:
            msg = f'Cannot resolve queryset class {queryset_class_path!r}: {error}'
            raise ValueError(msg) from error
    if not isinstance(owner, type) or not issubclass(owner, QuerySet):
        msg = (
            f'Queryset class path {queryset_class_path!r} does not name a '
            'QuerySet subclass.'
        )
        raise TypeError(msg)
    return owner
