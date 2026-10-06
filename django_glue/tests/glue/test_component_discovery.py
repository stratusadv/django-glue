from __future__ import annotations

from pathlib import Path

import pytest

from django_glue.exceptions import GlueComponentRegistrationError
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
