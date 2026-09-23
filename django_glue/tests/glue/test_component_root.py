from __future__ import annotations

import pytest

from django_glue.exceptions import GlueComponentRootError
from django_glue.glue.component_root import inject_component_root

ROOT_ATTRIBUTES = ' data-glue-address="a#1" data-glue-objects="[]"'


def inject(html: str) -> str:
    return inject_component_root(html, 'a#1', 'component.html', [])


@pytest.mark.parametrize(('html', 'root_start'), [
    ('<div>x</div>', '<div'),
    ('\n  <!-- note -->\n<div>x</div>\n', '<div'),
    ('<ul><li>a<li>b</ul>', '<ul'),
    ('<div><p>a<p>b</div>', '<div'),
    ('<table><tr><td>a<td>b</table>', '<table'),
    ('<div>a</p>b</div>', '<div'),
    ('<input type="text">', '<input type="text"'),
    ('<div><svg><path d="M0"/></svg></div>', '<div'),
])
def test_single_root_markup_is_accepted(html: str, root_start: str) -> None:
    assert f'{root_start}{ROOT_ATTRIBUTES}' in inject(html)


def test_self_closing_root_gets_attributes_before_the_slash() -> None:
    assert inject('<glue-marker />') == f'<glue-marker {ROOT_ATTRIBUTES}/>'


@pytest.mark.parametrize('prefix', ['\x0c\n', ' ', '\r'])
def test_attributes_land_inside_the_root_after_unusual_line_breaks(prefix: str) -> None:
    html = f'<!--{prefix}--><div>x</div>'

    assert inject(html) == f'<!--{prefix}--><div{ROOT_ATTRIBUTES}>x</div>'


@pytest.mark.parametrize('html', [
    '<div>a</div><div>b</div>',
    '<p>a<p>b',
    '<div>a',
    'text<div>x</div>',
    '&nbsp;<div>x</div>',
    '<div>x</div>&#160;',
    '',
])
def test_markup_without_exactly_one_closed_root_is_rejected(html: str) -> None:
    with pytest.raises(GlueComponentRootError):
        inject(html)
