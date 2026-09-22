from __future__ import annotations

import pytest

from django_glue.exceptions import GlueComponentRootError
from django_glue.glue.component.root_injection import inject_root_attributes

ATTRIBUTES = ' x-data="{ component: Glue.component.card_a3f9b2 }" data-glue="card_a3f9b2"'


def inject(html: str) -> str:
    return inject_root_attributes(
        html,
        ATTRIBUTES,
        component_name='card_a3f9b2',
        template_name='component/card.html',
    )


class TestInjection:
    def test_attributes_land_in_the_root_opening_tag(self) -> None:
        assert inject('<div class="card">hi</div>') == (
            f'<div class="card"{ATTRIBUTES}>hi</div>'
        )

    def test_leading_whitespace_and_comments_are_skipped(self) -> None:
        html = '\n  <!-- a note -->\n<div>hi</div>\n'

        assert f'<div{ATTRIBUTES}>' in inject(html)

    def test_a_doctype_is_skipped(self) -> None:
        assert f'<div{ATTRIBUTES}>' in inject('<!DOCTYPE html><div>hi</div>')

    def test_a_multiline_opening_tag_is_handled(self) -> None:
        html = '<div\n  class="card"\n  id="x"\n>hi</div>'

        assert inject(html) == (
            f'<div\n  class="card"\n  id="x"{ATTRIBUTES}>hi</div>'
        )

    def test_a_greater_than_inside_an_attribute_does_not_end_the_tag(self) -> None:
        """x-show="count > 0" must not be mistaken for the end of the tag."""
        html = '<div x-show="count > 0" class="card">hi</div>'

        result = inject(html)

        assert result == f'<div x-show="count > 0" class="card"{ATTRIBUTES}>hi</div>'

    def test_a_greater_than_in_a_single_quoted_attribute_is_handled(self) -> None:
        html = "<div x-show='a > b'>hi</div>"

        assert inject(html) == f"<div x-show='a > b'{ATTRIBUTES}>hi</div>"

    def test_a_self_closing_root_keeps_its_slash(self) -> None:
        assert inject('<img src="a.png" />') == f'<img src="a.png" {ATTRIBUTES[1:]}/>'

    def test_nested_elements_of_the_same_name_do_not_confuse_the_scan(self) -> None:
        html = '<div class="outer"><div>a</div><div>b</div></div>'

        assert inject(html) == (
            f'<div class="outer"{ATTRIBUTES}><div>a</div><div>b</div></div>'
        )

    def test_a_script_body_is_not_scanned_as_markup(self) -> None:
        """A '<' inside a script is text, not a tag."""
        html = '<div><script>if (a < b) { go() }</script></div>'

        assert inject(html) == f'<div{ATTRIBUTES}><script>if (a < b) {{ go() }}</script></div>'

    def test_a_void_element_inside_the_root_does_not_unbalance_it(self) -> None:
        html = '<div>a<br>b<img src="x"></div>'

        assert inject(html).startswith(f'<div{ATTRIBUTES}>')

    def test_a_trailing_comment_is_not_a_second_root(self) -> None:
        html = '<div>hi</div>\n<!-- trailing -->\n'

        assert f'<div{ATTRIBUTES}>' in inject(html)


class TestSingleRootEnforcement:
    def test_two_root_elements_are_rejected(self) -> None:
        with pytest.raises(GlueComponentRootError, match='more than one root'):
            inject('<div>a</div><div>b</div>')

    def test_text_outside_the_root_is_rejected(self) -> None:
        with pytest.raises(GlueComponentRootError, match='text outside its root'):
            inject('stray text <div>a</div>')

    def test_trailing_text_after_the_root_is_rejected(self) -> None:
        with pytest.raises(GlueComponentRootError, match='more than one root'):
            inject('<div>a</div> trailing')

    def test_empty_output_is_rejected(self) -> None:
        with pytest.raises(GlueComponentRootError, match='rendered no HTML'):
            inject('   \n  ')

    def test_an_unclosed_root_is_rejected(self) -> None:
        with pytest.raises(GlueComponentRootError, match='unclosed'):
            inject('<div>a')

    def test_an_unterminated_opening_tag_is_rejected(self) -> None:
        with pytest.raises(GlueComponentRootError, match='unterminated opening tag'):
            inject('<div class="x"')

    def test_an_unterminated_comment_is_rejected(self) -> None:
        with pytest.raises(GlueComponentRootError, match='unterminated HTML comment'):
            inject('<!-- never closed <div>a</div>')

    def test_the_error_names_the_template(self) -> None:
        with pytest.raises(GlueComponentRootError, match='component/card.html'):
            inject('<div>a</div><div>b</div>')
