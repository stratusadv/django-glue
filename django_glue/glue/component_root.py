from __future__ import annotations

import json
from html.parser import HTMLParser
from typing import Any

from django.utils.html import escape

from django_glue.encoders import GlueResponseJSONEncoder
from django_glue.exceptions import GlueComponentRootError


VOID_ELEMENTS = frozenset({
    'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link',
    'meta', 'param', 'source', 'track', 'wbr',
})


class _RootScanner(HTMLParser):
    """Find the single root element of rendered component HTML.

    Open elements are tracked as a stack: an end tag closes everything up to
    its matching open element, so optional end tags (``<li>``, ``<p>``,
    ``<td>``) may be omitted inside the root, and an end tag matching nothing
    is ignored, as browsers do.
    """

    def __init__(self, template_name: str) -> None:
        super().__init__(convert_charrefs=False)
        self.template_name = template_name
        self.open_elements: list[str] = []
        self.roots = 0
        self.start: tuple[int, int] | None = None
        self.raw_start: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        _ = attrs
        self._count_root()
        if tag not in VOID_ELEMENTS:
            self.open_elements.append(tag)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        _ = tag, attrs
        self._count_root()

    def handle_endtag(self, tag: str) -> None:
        if tag not in self.open_elements:
            return
        while self.open_elements.pop() != tag:
            pass

    def handle_data(self, data: str) -> None:
        if data.strip():
            self._reject_outside_text()

    def handle_entityref(self, name: str) -> None:
        _ = name
        self._reject_outside_text()

    def handle_charref(self, name: str) -> None:
        _ = name
        self._reject_outside_text()

    def _count_root(self) -> None:
        if self.open_elements:
            return
        self.roots += 1
        if self.start is None:
            self.start = self.getpos()
            self.raw_start = self.get_starttag_text()

    def _reject_outside_text(self) -> None:
        if not self.open_elements:
            raise GlueComponentRootError(
                f"Component template '{self.template_name}' renders text outside its root."
            )


def inject_component_root(
    html: str,
    address: str,
    template_name: str,
    entries: list[dict[str, Any]],
) -> str:
    """Mark the component's single root with its address and the flat
    addressed entries of its subtree, root first, so a stamp rendered after
    ``{% django_glue_init %}`` still introduces its children (state-model.md
    §10 "Page load")."""
    scanner = _RootScanner(template_name)
    scanner.feed(html)
    scanner.close()
    if (
        scanner.roots != 1
        or scanner.open_elements
        or scanner.start is None
        or scanner.raw_start is None
    ):
        raise GlueComponentRootError(
            f"Component template '{template_name}' must render exactly one closed root element."
        )
    line, column = scanner.start
    start = sum(len(part) + 1 for part in html.split('\n')[:line - 1]) + column
    raw = scanner.raw_start
    insert_at = start + len(raw) - (2 if raw.endswith('/>') else 1)
    encoded_entries = escape(json.dumps(entries, cls=GlueResponseJSONEncoder))
    attributes = f' data-glue-address="{escape(address)}" data-glue-objects="{encoded_entries}"'
    return f'{html[:insert_at]}{attributes}{html[insert_at:]}'
