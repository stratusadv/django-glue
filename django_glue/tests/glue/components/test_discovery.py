from __future__ import annotations

from pathlib import Path

import pytest
from django.template import Context, Template

from django_glue.exceptions import GlueComponentRegistrationError
from django_glue.glue.components import component_registry
from django_glue.glue.context import GlueContextManager
from django_glue.glue.policy import GluePolicy
from django_glue.glue.components.discovery import check_components_setting, resolve_component
from test_project.gorilla.components import CounterCardComponent

COMPONENT_SOURCE = (
    'from django_glue import Glue\n\n\n'
    'class {name}(Glue.Component):\n'
    "    template = 'glue_template_test.html'\n"
)


def write_package(root: Path, dotted: str, components_source: str) -> None:
    directory = root
    for part in dotted.split('.'):
        directory = directory / part
        directory.mkdir(exist_ok=True)
        (directory / '__init__.py').touch()
    (directory / 'components.py').write_text(components_source)


def write_nested_module(root: Path, path: str, name: str) -> None:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(COMPONENT_SOURCE.format(name=name))


@pytest.fixture
def on_sys_path(tmp_path, monkeypatch) -> Path:
    monkeypatch.syspath_prepend(str(tmp_path))
    return tmp_path


def test_a_directory_resolves_a_tag_relative_to_it(settings) -> None:
    settings.DJANGO_GLUE_COMPONENTS = {'DIRS': [settings.BASE_DIR / 'test_project'], 'APP_DIRS': False}

    assert resolve_component('gorilla/counter_card') is CounterCardComponent


def test_directories_default_to_base_dir(settings) -> None:
    settings.DJANGO_GLUE_COMPONENTS = {'APP_DIRS': False}

    assert resolve_component('test_project/gorilla/counter_card') is CounterCardComponent


def test_an_installed_app_resolves_a_tag_by_its_package_path(settings) -> None:
    settings.DJANGO_GLUE_COMPONENTS = {'DIRS': []}

    assert resolve_component('test_project/gorilla/counter_card') is CounterCardComponent


def test_app_lookup_is_off_when_app_dirs_is_false(settings) -> None:
    settings.DJANGO_GLUE_COMPONENTS = {'DIRS': [], 'APP_DIRS': False}

    with pytest.raises(GlueComponentRegistrationError, match='searched no components module'):
        resolve_component('test_project/gorilla/counter_card')


def test_a_package_outside_the_installed_apps_is_not_searched(settings, on_sys_path) -> None:
    write_package(on_sys_path, 'loose_parts', COMPONENT_SOURCE.format(name='WidgetComponent'))
    settings.DJANGO_GLUE_COMPONENTS = {'DIRS': []}

    with pytest.raises(GlueComponentRegistrationError, match='searched no components module'):
        resolve_component('loose_parts/widget')


def test_a_directory_overrides_an_installed_app_component(settings, on_sys_path) -> None:
    write_package(
        on_sys_path,
        'app_overrides.test_project.gorilla',
        COMPONENT_SOURCE.format(name='CounterCardComponent'),
    )
    settings.DJANGO_GLUE_COMPONENTS = {'DIRS': [on_sys_path / 'app_overrides']}

    resolved = resolve_component('test_project/gorilla/counter_card')

    assert resolved.__module__ == 'app_overrides.test_project.gorilla.components'


def test_a_location_without_the_class_falls_through_to_the_next(settings, on_sys_path) -> None:
    write_package(
        on_sys_path,
        'partial_overrides.test_project.gorilla',
        COMPONENT_SOURCE.format(name='OtherCardComponent'),
    )
    settings.DJANGO_GLUE_COMPONENTS = {'DIRS': [on_sys_path / 'partial_overrides']}

    assert resolve_component('test_project/gorilla/counter_card') is CounterCardComponent


def test_an_unresolved_tag_names_every_module_searched(settings, on_sys_path) -> None:
    write_package(
        on_sys_path,
        'named_overrides.test_project.gorilla',
        COMPONENT_SOURCE.format(name='OtherCardComponent'),
    )
    settings.DJANGO_GLUE_COMPONENTS = {'DIRS': [on_sys_path / 'named_overrides']}

    with pytest.raises(GlueComponentRegistrationError) as caught:
        resolve_component('test_project/gorilla/missing_card')

    message = str(caught.value)
    assert 'named_overrides.test_project.gorilla.components' in message
    assert "'test_project.gorilla.components'" in message


def test_a_directory_whose_components_cannot_be_imported_fails_instead_of_being_skipped(
    settings, tmp_path,
) -> None:
    write_package(
        tmp_path,
        'stray_overrides.test_project.gorilla',
        COMPONENT_SOURCE.format(name='CounterCardComponent'),
    )
    settings.DJANGO_GLUE_COMPONENTS = {'DIRS': [tmp_path / 'stray_overrides']}

    with pytest.raises(GlueComponentRegistrationError) as caught:
        resolve_component('test_project/gorilla/counter_card')

    message = str(caught.value)
    assert 'cannot be imported' in message
    assert str(tmp_path / 'stray_overrides') in message
    assert 'sys.path' in message


def test_a_nested_directory_is_part_of_the_tag(settings, on_sys_path) -> None:
    write_nested_module(on_sys_path, 'nest_one/components/cards/any_file.py', 'WidgetComponent')
    settings.DJANGO_GLUE_COMPONENTS = {'DIRS': [on_sys_path], 'APP_DIRS': False}

    resolved = resolve_component('nest_one/cards/widget')

    assert resolved.__module__ == 'nest_one.components.cards.any_file'


def test_every_nested_directory_is_part_of_the_tag(settings, on_sys_path) -> None:
    write_nested_module(on_sys_path, 'nest_two/components/cards/small/any_file.py', 'WidgetComponent')
    settings.DJANGO_GLUE_COMPONENTS = {'DIRS': [on_sys_path], 'APP_DIRS': False}

    resolved = resolve_component('nest_two/cards/small/widget')

    assert resolved.__module__ == 'nest_two.components.cards.small.any_file'
    with pytest.raises(GlueComponentRegistrationError, match="in 'nest_two.components.cards'"):
        resolve_component('nest_two/cards/widget')


def test_a_tag_without_the_nested_directory_does_not_find_the_component(
    settings, on_sys_path,
) -> None:
    write_nested_module(on_sys_path, 'nest_three/components/cards/any_file.py', 'WidgetComponent')
    settings.DJANGO_GLUE_COMPONENTS = {'DIRS': [on_sys_path], 'APP_DIRS': False}

    with pytest.raises(GlueComponentRegistrationError, match="in 'nest_three.components'"):
        resolve_component('nest_three/widget')


def test_a_nested_directory_of_an_installed_app_is_part_of_the_tag(
    settings, on_sys_path,
) -> None:
    write_nested_module(on_sys_path, 'nest_app/components/cards/any_file.py', 'WidgetComponent')
    (on_sys_path / 'nest_app' / '__init__.py').touch()
    settings.INSTALLED_APPS = [*settings.INSTALLED_APPS, 'nest_app']
    settings.DJANGO_GLUE_COMPONENTS = {'DIRS': []}

    resolved = resolve_component('nest_app/cards/widget')

    assert resolved.__module__ == 'nest_app.components.cards.any_file'


def test_a_tag_that_two_readings_resolve_is_ambiguous(settings, on_sys_path) -> None:
    write_package(on_sys_path, 'nest_both.cards', COMPONENT_SOURCE.format(name='WidgetComponent'))
    write_nested_module(on_sys_path, 'nest_both/components/cards/any_file.py', 'WidgetComponent')
    settings.DJANGO_GLUE_COMPONENTS = {'DIRS': [on_sys_path], 'APP_DIRS': False}

    with pytest.raises(GlueComponentRegistrationError) as caught:
        resolve_component('nest_both/cards/widget')

    message = str(caught.value)
    assert 'ambiguous' in message
    assert 'nest_both.cards.components.WidgetComponent' in message
    assert 'nest_both.components.cards.any_file.WidgetComponent' in message


def test_a_class_two_readings_both_reach_is_not_ambiguous(settings, on_sys_path) -> None:
    write_nested_module(on_sys_path, 'nest_shared/components/cards/any_file.py', 'WidgetComponent')
    write_package(
        on_sys_path,
        'nest_shared.cards',
        'from nest_shared.components.cards.any_file import WidgetComponent\n',
    )
    settings.DJANGO_GLUE_COMPONENTS = {'DIRS': [on_sys_path], 'APP_DIRS': False}

    resolved = resolve_component('nest_shared/cards/widget')

    assert resolved.__module__ == 'nest_shared.components.cards.any_file'


def test_a_package_that_imports_a_nested_class_keeps_the_short_tag(settings, on_sys_path) -> None:
    write_nested_module(on_sys_path, 'nest_export/components/cards/any_file.py', 'WidgetComponent')
    (on_sys_path / 'nest_export' / 'components' / '__init__.py').write_text(
        'from nest_export.components.cards.any_file import WidgetComponent\n'
    )
    settings.DJANGO_GLUE_COMPONENTS = {'DIRS': [on_sys_path], 'APP_DIRS': False}

    assert resolve_component('nest_export/widget') is resolve_component('nest_export/cards/widget')


def test_a_directory_left_beside_a_components_module_is_not_a_nested_directory(
    settings, on_sys_path,
) -> None:
    write_package(on_sys_path, 'nest_stale', COMPONENT_SOURCE.format(name='WidgetComponent'))
    (on_sys_path / 'nest_stale' / 'components' / 'cards').mkdir(parents=True)
    settings.DJANGO_GLUE_COMPONENTS = {'DIRS': [on_sys_path], 'APP_DIRS': False}

    with pytest.raises(GlueComponentRegistrationError, match='no class named'):
        resolve_component('nest_stale/cards/widget')


def test_a_dotted_path_names_the_class_directly(on_sys_path) -> None:
    write_nested_module(on_sys_path, 'dotted_one/anywhere/widgets.py', 'WidgetComponent')

    resolved = component_registry.from_tag_name('dotted_one.anywhere.widgets.WidgetComponent')

    assert resolved.__module__ == 'dotted_one.anywhere.widgets'
    assert resolved.__name__ == 'WidgetComponent'


def test_the_template_tag_stamps_a_component_by_its_dotted_path(mock_request) -> None:
    html = Template(
        "{% load django_glue %}"
        "{% glue_component 'test_project.gorilla.components.CounterCardComponent' start=3 %}"
    ).render(Context({'request': mock_request}))

    entry = GlueContextManager(mock_request).serialized_objects[0]
    assert 'data-glue-address=' in html
    assert GluePolicy.from_token(entry['policy_token']).identity['component_id'] == (
        'test_project.gorilla.components.CounterCardComponent'
    )


def test_a_dotted_path_to_something_that_is_not_a_component_is_refused() -> None:
    with pytest.raises(GlueComponentRegistrationError, match='not a Glue component'):
        component_registry.from_tag_name('pathlib.Path')


@pytest.mark.parametrize('tag_name', ['Gorilla/CounterCard', 'gorilla/counter.card', 'gorilla-card', ''])
def test_a_tag_that_is_neither_a_path_nor_a_dotted_path_is_invalid(tag_name) -> None:
    with pytest.raises(GlueComponentRegistrationError, match='Invalid Glue component tag name'):
        component_registry.from_tag_name(tag_name)


def test_check_rejects_the_removed_components_root_setting(settings) -> None:
    settings.DJANGO_GLUE_COMPONENTS_ROOT = 'app'

    errors = check_components_setting()

    assert [error.id for error in errors] == ['django_glue.E004']
    assert "DJANGO_GLUE_COMPONENTS = {'DIRS': ['app']}" in errors[0].hint


@pytest.mark.parametrize('configured', [
    ['app'],
    {'DIRS': 'app'},
    {'APP_DIRS': 'yes'},
    {'DIRS': [], 'LOADERS': []},
])
def test_check_rejects_a_malformed_components_setting(settings, configured) -> None:
    settings.DJANGO_GLUE_COMPONENTS = configured

    assert [error.id for error in check_components_setting()] == ['django_glue.E005']


def test_check_accepts_a_valid_or_missing_components_setting(settings) -> None:
    assert check_components_setting() == []

    del settings.DJANGO_GLUE_COMPONENTS
    assert check_components_setting() == []
