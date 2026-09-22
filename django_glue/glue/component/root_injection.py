from __future__ import annotations

from django_glue.exceptions import GlueComponentRootError

# Elements whose content is raw text, where a '<' does not open a tag.
RAWTEXT_ELEMENTS = frozenset({'script', 'style'})

# Elements that never have a closing tag, so they cannot nest.
VOID_ELEMENTS = frozenset({
    'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
    'link', 'meta', 'param', 'source', 'track', 'wbr',
})

_QUOTES = frozenset({'"', "'"})


def inject_root_attributes(
    html: str,
    attributes: str,
    *,
    component_name: str,
    template_name: str,
) -> str:
    """Insert Glue's attributes into a component's root element.

    A component template is ordinary HTML with no Glue marker in it, so the
    binding and root marker are added to whatever element it rendered. This is
    the same shape Livewire uses: it requires one root element per component and
    injects ``wire:id`` into it.

    The scan is narrow by construction -- one fragment, one root -- unlike a
    scanner over arbitrary page templates. The single-root rule is what keeps it
    unambiguous, so it is enforced here rather than left advisory.
    """
    start = _skip_non_element(html, 0, template_name)

    if start >= len(html):
        msg = (
            f"Component template '{template_name}' rendered no HTML. A component "
            f'must render exactly one root element.'
        )
        raise GlueComponentRootError(msg)

    if html[start] != '<':
        msg = (
            f"Component template '{template_name}' renders text outside its root "
            f'element. A component must render exactly one root element, because '
            f'that element carries its Alpine binding and is its morph boundary.'
        )
        raise GlueComponentRootError(msg)

    element_name = _read_element_name(html, start, template_name)
    open_tag_end = _find_open_tag_end(html, start, template_name)

    _require_single_root(html, start, open_tag_end, element_name, template_name)

    insert_at = open_tag_end
    if html[insert_at - 1] == '/':
        insert_at -= 1

    # Whitespace before the tag's close is insignificant, and the attributes
    # supply their own leading space -- so trim it rather than emit a multiline
    # tag broken across the insertion or a doubled space before '/>'.
    return f'{html[:insert_at].rstrip()}{attributes}{html[insert_at:]}'


def _skip_non_element(html: str, index: int, template_name: str) -> int:
    """Advance past whitespace, comments, and doctype declarations."""
    while index < len(html):
        if html[index].isspace():
            index += 1
            continue

        if html.startswith('<!--', index):
            end = html.find('-->', index)
            if end == -1:
                msg = f"Component template '{template_name}' has an unterminated HTML comment."
                raise GlueComponentRootError(msg)
            index = end + 3
            continue

        if html.startswith('<!', index) or html.startswith('<?', index):
            end = html.find('>', index)
            if end == -1:
                msg = f"Component template '{template_name}' has an unterminated declaration."
                raise GlueComponentRootError(msg)
            index = end + 1
            continue

        break

    return index


def _read_element_name(html: str, start: int, template_name: str) -> str:
    index = start + 1
    end = index

    while end < len(html) and (html[end].isalnum() or html[end] in '-_:'):
        end += 1

    if end == index:
        msg = (
            f"Component template '{template_name}' does not start with an HTML "
            f'element. A component must render exactly one root element.'
        )
        raise GlueComponentRootError(msg)

    return html[index:end].lower()


def _find_open_tag_end(html: str, start: int, template_name: str) -> int:
    """Return the index of the '>' closing this opening tag.

    Quoted attribute values are skipped, so a '>' inside one -- as in
    ``x-show="count > 0"`` -- does not end the tag.
    """
    quote = None
    index = start + 1

    while index < len(html):
        character = html[index]

        if quote is not None:
            if character == quote:
                quote = None
        elif character in _QUOTES:
            quote = character
        elif character == '>':
            return index

        index += 1

    msg = f"Component template '{template_name}' has an unterminated opening tag."
    raise GlueComponentRootError(msg)


def _require_single_root(
    html: str,
    start: int,
    open_tag_end: int,
    element_name: str,
    template_name: str,
) -> None:
    root_end = _find_element_end(
        html,
        open_tag_end,
        element_name,
        self_closing=html[open_tag_end - 1] == '/',
        template_name=template_name,
    )
    trailing = _skip_non_element(html, root_end, template_name)

    if trailing < len(html):
        msg = (
            f"Component template '{template_name}' renders more than one root "
            f'element. Livewire-style injection and morphing both need exactly '
            f'one: the root carries the Alpine binding and is the morph boundary. '
            f'Wrap the content in a single element.'
        )
        raise GlueComponentRootError(msg)

    _ = start


def _find_element_end(
    html: str,
    open_tag_end: int,
    element_name: str,
    *,
    self_closing: bool,
    template_name: str,
) -> int:
    if self_closing or element_name in VOID_ELEMENTS:
        return open_tag_end + 1

    if element_name in RAWTEXT_ELEMENTS:
        return _skip_rawtext(html, open_tag_end + 1, element_name, template_name)

    depth = 1
    index = open_tag_end + 1

    while index < len(html):
        if html[index] != '<':
            index += 1
            continue

        if html.startswith('<!--', index):
            end = html.find('-->', index)
            index = len(html) if end == -1 else end + 3
            continue

        if html.startswith('</', index):
            closing_name = _peek_name(html, index + 2)
            tag_end = _find_open_tag_end(html, index, template_name)
            if closing_name == element_name:
                depth -= 1
                if depth == 0:
                    return tag_end + 1
            index = tag_end + 1
            continue

        opening_name = _peek_name(html, index + 1)
        tag_end = _find_open_tag_end(html, index, template_name)

        if opening_name in RAWTEXT_ELEMENTS:
            index = _skip_rawtext(html, tag_end + 1, opening_name, template_name)
            continue

        if opening_name == element_name and html[tag_end - 1] != '/':
            depth += 1

        index = tag_end + 1

    msg = (
        f"Component template '{template_name}' has an unclosed <{element_name}> "
        f'root element.'
    )
    raise GlueComponentRootError(msg)


def _skip_rawtext(html: str, index: int, element_name: str, template_name: str) -> int:
    """Skip a script/style body, where '<' does not open a tag."""
    closing = f'</{element_name}'
    end = html.lower().find(closing, index)

    if end == -1:
        msg = f"Component template '{template_name}' has an unclosed <{element_name}> element."
        raise GlueComponentRootError(msg)

    return _find_open_tag_end(html, end, template_name) + 1


def _peek_name(html: str, index: int) -> str:
    end = index

    while end < len(html) and (html[end].isalnum() or html[end] in '-_:'):
        end += 1

    return html[index:end].lower()
