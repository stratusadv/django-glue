from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from django_glue import Glue
from django_glue.glue.components import Component
from django_glue.glue.components.session import ComponentSession
from django_glue.tests.glue.test_callable_parameters import call_context

if TYPE_CHECKING:
    from django.http import HttpRequest
    from django.test import RequestFactory


class SessionProbeComponent(Component):
    template = 'glue_template_test.html'

    @Glue.attr
    def record(self) -> None:
        self.session['last'] = 'recorded'


class SessionAutoComponent(Component):
    template = 'glue_template_test.html'

    @Glue.attr
    def record(self) -> None:
        self.session['auto'] = 'recorded'

    @Glue.attr
    def noop(self) -> None:
        pass


class SessionMountComponent(Component):
    template = 'glue_template_test.html'

    def mount(self) -> None:
        self.session['mounted'] = True


class SessionFailComponent(Component):
    template = 'glue_template_test.html'

    @Glue.attr
    def explode(self) -> None:
        self.session['lost'] = 'value'
        msg = 'boom'
        raise ValueError(msg)


def test_fresh_namespace_loads_empty(mock_request: HttpRequest) -> None:
    session = ComponentSession(mock_request, 'fresh')

    assert len(session) == 0
    assert 'nope' not in session
    assert session.get('nope') is None


def test_set_round_trips_into_a_second_session(mock_request: HttpRequest) -> None:
    first = ComponentSession(mock_request, 'round_trip')
    first['count'] = 1
    first['name'] = 'nathan'

    second = ComponentSession(mock_request, 'round_trip')

    assert dict(second) == {'count': 1, 'name': 'nathan'}
    assert second['count'] == 1


def test_reading_a_clean_namespace_leaves_the_session_unmodified(mock_request: HttpRequest) -> None:
    session = ComponentSession(mock_request, 'clean')

    assert 'nope' not in session
    assert session.get('nope') is None
    assert mock_request.session.modified is False


def test_mutation_marks_the_session_modified(mock_request: HttpRequest) -> None:
    session = ComponentSession(mock_request, 'once')

    assert mock_request.session.modified is False
    session['a'] = 1

    assert mock_request.session.modified is True


def test_setting_the_same_value_does_not_mark_modified(mock_request: HttpRequest) -> None:
    session = ComponentSession(mock_request, 'same')
    session['count'] = 1
    session['data'] = {'x': 1}

    mock_request.session.modified = False
    session['count'] = 1
    session['data'] = {'x': 1}

    assert mock_request.session.modified is False


def test_overwriting_with_a_different_value_marks_modified(mock_request: HttpRequest) -> None:
    session = ComponentSession(mock_request, 'overwrite')
    session['count'] = 1
    mock_request.session.modified = False

    session['count'] = 2

    assert mock_request.session.modified is True


def test_delete_marks_modified_and_persists(mock_request: HttpRequest) -> None:
    first = ComponentSession(mock_request, 'delete')
    first['a'] = 1
    first['b'] = 2

    second = ComponentSession(mock_request, 'delete')
    del second['a']

    third = ComponentSession(mock_request, 'delete')

    assert dict(third) == {'b': 2}
    assert mock_request.session.modified is True


def test_namespaces_are_isolated(mock_request: HttpRequest) -> None:
    alpha = ComponentSession(mock_request, 'alpha')
    beta = ComponentSession(mock_request, 'beta')
    alpha['shared'] = 'alpha'
    beta['shared'] = 'beta'

    assert ComponentSession(mock_request, 'alpha')['shared'] == 'alpha'
    assert ComponentSession(mock_request, 'beta')['shared'] == 'beta'


def test_non_string_keys_raise_type_error(mock_request: HttpRequest) -> None:
    session = ComponentSession(mock_request, 'keys')

    with pytest.raises(TypeError):
        session[1] = 'x'  # type: ignore[index]
    with pytest.raises(TypeError):
        del session[1]  # type: ignore[index]
    assert len(session) == 0


def test_stored_value_that_is_not_a_dict_loads_empty(mock_request: HttpRequest) -> None:
    session = ComponentSession(mock_request, 'corrupt')
    mock_request.session[session._key] = 'not-a-dict'

    assert len(session) == 0


def test_component_session_uses_the_class_qualname(mock_request: HttpRequest) -> None:
    component = Glue.object(mock_request, SessionProbeComponent())
    session = component.session

    assert session.namespace == 'SessionProbeComponent'
    assert session is component.session


def test_component_session_requires_a_bound_component() -> None:
    component = SessionProbeComponent()

    with pytest.raises(RuntimeError, match='unbound component'):
        _ = component.session


def test_session_value_survives_to_a_second_request(
    mock_request: HttpRequest, request_factory: RequestFactory
) -> None:
    component = Glue.object(mock_request, SessionProbeComponent())
    context = call_context(component, 'record')
    reconstructed = SessionProbeComponent.from_attribute_call_resolver_context(context)
    reconstructed.process_attribute_call(context)

    second_request = request_factory.get('/')
    second_request.session = mock_request.session
    fresh = Glue.object(second_request, SessionProbeComponent())

    assert fresh.session['last'] == 'recorded'


def test_mount_write_is_visible_on_introduction(mock_request: HttpRequest) -> None:
    Glue.object(mock_request, SessionMountComponent())

    assert ComponentSession(mock_request, 'SessionMountComponent')['mounted'] is True


def test_callable_write_reaches_the_session(mock_request: HttpRequest) -> None:
    component = Glue.object(mock_request, SessionAutoComponent())
    context = call_context(component, 'record')
    reconstructed = SessionAutoComponent.from_attribute_call_resolver_context(context)
    reconstructed.process_attribute_call(context)

    assert ComponentSession(mock_request, 'SessionAutoComponent')['auto'] == 'recorded'


def test_interaction_without_a_change_leaves_the_session_clean(mock_request: HttpRequest) -> None:
    component = Glue.object(mock_request, SessionAutoComponent())
    context = call_context(component, 'noop')
    reconstructed = SessionAutoComponent.from_attribute_call_resolver_context(context)
    reconstructed.process_attribute_call(context)

    assert mock_request.session.modified is False


def test_failed_call_keeps_its_session_write(mock_request: HttpRequest) -> None:
    component = Glue.object(mock_request, SessionFailComponent())
    context = call_context(component, 'explode')
    reconstructed = SessionFailComponent.from_attribute_call_resolver_context(context)

    with pytest.raises(ValueError, match='boom'):
        reconstructed.process_attribute_call(context)

    assert ComponentSession(mock_request, 'SessionFailComponent')['lost'] == 'value'
