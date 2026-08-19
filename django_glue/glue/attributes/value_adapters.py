from __future__ import annotations

from typing import Any, Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from django_glue.glue.attributes.declared import DeclaredAttribute


class GlueValueAdapter(Protocol):
    """Recognizes a plain assigned value and converts it into its Glue representation.

    DeclaredAttribute.__set__ tries each adapter in turn (see
    DEFAULT_VALUE_ADAPTERS); the first whose applies_to() matches wins.
    """

    def applies_to(self, value: Any) -> bool:
        """Whether this adapter should handle the given assigned value."""
        ...

    def adapt(self, value: Any, *, attribute: DeclaredAttribute, instance: Any) -> Any:
        """Convert value into its Glue representation.

        instance is the BaseGlue object the attribute is being set on --
        access for any Glue objects built here should come from
        instance.access (the actual runtime access for this request/user),
        not from the attribute's own declared required_access, which only
        gates who may read/write the attribute itself.
        """
        ...


class SequenceAdapter:
    """Adapts a plain, non-empty list assignment into a SequenceGlue.

    Items already glued (BaseGlue instances) are used as-is; raw items are
    converted via the owning attribute's glue_factory. The sequence and
    its raw items inherit the owning instance's runtime access (instance.access)
    so permissions propagate the same way they did when this was hand-built
    (e.g. TimeEntryDayGlue used to pass self.access to each ModelGlue it built).
    """

    def applies_to(self, value: Any) -> bool:
        return isinstance(value, list) and len(value) > 0

    def adapt(self, value: Any, *, attribute: DeclaredAttribute, instance: Any) -> Any:
        from django_glue.glue.sequence import SequenceGlue  # noqa: PLC0415

        attribute._get_storage_name()  # noqa: SLF001 -- raises if unbound; guarantees attribute.name is set
        return SequenceGlue.from_item_factory(
            value,
            name=attribute.name,  # type: ignore[arg-type]
            access=instance.access,
            glue_factory=attribute.glue_factory,
        )


DEFAULT_VALUE_ADAPTERS: list[GlueValueAdapter] = [
    SequenceAdapter(),
]
