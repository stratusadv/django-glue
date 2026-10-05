from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from django.core.cache import cache

from django_glue import Glue
from django_glue.glue.component import Component
from django_glue.glue.component_session import ComponentSession

from django_glue.tests.glue.test_callable_parameters import call_context

if TYPE_CHECKING:
    from collections.abc import Iterator

    from django.http import HttpRequest


@pytest.fixture(autouse=True)
def _flush_component_session_cache() -> Iterator[None]:
    cache.clear()
    yield
    cache.clear()


class SessionProbeComponent(Component):
    template = 'glue_template_test.html'

    @Glue.attr
    def record(self) -> None:
        self.session['last'] = 'recorded'
        self.session.save()


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


def test_set_save_round_trips_into_a_second_session(mock_request: HttpRequest) -> None:
    first = ComponentSession(mock_request, 'round_trip')
    first['count'] = 1
    first['name'] = 'nathan'
    first.save()

    second = ComponentSession(mock_request, 'round_trip')

    assert dict(second) == {'count': 1, 'name': 'nathan'}
    assert second['count'] == 1


def test_save_on_clean_namespace_performs_no_write(
    mock_request: HttpRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    written: list[str] = []
    real_set = cache.set

    def spy(key: Any, *args: Any, **kwargs: Any) -> Any:
        written.append(key)
        return real_set(key, *args, **kwargs)

    monkeypatch.setattr(cache, 'set', spy)

    session = ComponentSession(mock_request, 'clean')
    session.save()

    assert written == []


def test_save_after_a_mutation_writes_once(
    mock_request: HttpRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    written: list[str] = []
    real_set = cache.set

    def spy(key: Any, *args: Any, **kwargs: Any) -> Any:
        written.append(key)
        return real_set(key, *args, **kwargs)

    monkeypatch.setattr(cache, 'set', spy)

    session = ComponentSession(mock_request, 'once')
    session['a'] = 1
    session.save()
    assert session.is_dirty is False
    session.save()

    assert len(written) == 1


def test_delete_marks_dirty_and_persists(mock_request: HttpRequest) -> None:
    first = ComponentSession(mock_request, 'delete')
    first['a'] = 1
    first['b'] = 2
    first.save()

    second = ComponentSession(mock_request, 'delete')
    del second['a']
    second.save()

    third = ComponentSession(mock_request, 'delete')

    assert dict(third) == {'b': 2}


def test_discard_deletes_the_entry(mock_request: HttpRequest) -> None:
    first = ComponentSession(mock_request, 'discard')
    first['a'] = 1
    first.save()
    first.discard()

    second = ComponentSession(mock_request, 'discard')

    assert len(second) == 0


def test_namespaces_are_isolated(mock_request: HttpRequest) -> None:
    alpha = ComponentSession(mock_request, 'alpha')
    beta = ComponentSession(mock_request, 'beta')
    alpha['shared'] = 'alpha'
    beta['shared'] = 'beta'
    alpha.save()
    beta.save()

    assert ComponentSession(mock_request, 'alpha')['shared'] == 'alpha'
    assert ComponentSession(mock_request, 'beta')['shared'] == 'beta'


def test_non_string_keys_raise_type_error(mock_request: HttpRequest) -> None:
    session = ComponentSession(mock_request, 'keys')

    with pytest.raises(TypeError):
        session[1] = 'x'  # type: ignore[index]
    with pytest.raises(TypeError):
        del session[1]  # type: ignore[index]
    assert len(session) == 0


def test_cached_value_that_is_not_a_dict_loads_empty(mock_request: HttpRequest) -> None:
    session = ComponentSession(mock_request, 'corrupt')
    cache.set(session._key, 'not-a-dict')

    assert len(session) == 0


def test_setting_the_same_value_does_not_mark_dirty(
    mock_request: HttpRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    written: list[str] = []
    real_set = cache.set

    def spy(key: Any, *args: Any, **kwargs: Any) -> Any:
        written.append(key)
        return real_set(key, *args, **kwargs)

    monkeypatch.setattr(cache, 'set', spy)

    session = ComponentSession(mock_request, 'same')
    session['count'] = 1
    session['data'] = {'x': 1}
    session.save()

    session['count'] = 1
    session['data'] = {'x': 1}
    session.save()

    assert session.is_dirty is False
    assert len(written) == 1


def test_overwriting_with_a_different_value_marks_dirty(mock_request: HttpRequest) -> None:
    session = ComponentSession(mock_request, 'overwrite')
    session['count'] = 1
    session.save()

    session['count'] = 2

    assert session.is_dirty is True


def test_component_session_uses_the_class_qualname(mock_request: HttpRequest) -> None:
    component = Glue.object(mock_request, SessionProbeComponent())
    session = component.session

    assert session.namespace == 'SessionProbeComponent'
    assert session is component.session


def test_component_session_requires_a_bound_component() -> None:
    component = SessionProbeComponent()

    with pytest.raises(RuntimeError, match='unbound component'):
        _ = component.session


def test_session_value_survives_to_a_second_request(mock_request: HttpRequest) -> None:
    component = Glue.object(mock_request, SessionProbeComponent())
    context = call_context(component, 'record')
    reconstructed = SessionProbeComponent.from_attribute_call_resolver_context(context)
    reconstructed.process_attribute_call(context)

    fresh = Glue.object(mock_request, SessionProbeComponent())

    assert fresh.session['last'] == 'recorded'


def test_mount_write_is_flushed_on_introduction(mock_request: HttpRequest) -> None:
    Glue.object(mock_request, SessionMountComponent())

    assert ComponentSession(mock_request, 'SessionMountComponent')['mounted'] is True


def test_callable_write_is_flushed_without_save(mock_request: HttpRequest) -> None:
    component = Glue.object(mock_request, SessionAutoComponent())
    context = call_context(component, 'record')
    reconstructed = SessionAutoComponent.from_attribute_call_resolver_context(context)
    reconstructed.process_attribute_call(context)

    assert ComponentSession(mock_request, 'SessionAutoComponent')['auto'] == 'recorded'


def test_interaction_without_a_change_performs_no_cache_write(
    mock_request: HttpRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    written: list[str] = []
    real_set = cache.set

    def spy(key: Any, *args: Any, **kwargs: Any) -> Any:
        written.append(key)
        return real_set(key, *args, **kwargs)

    monkeypatch.setattr(cache, 'set', spy)

    component = Glue.object(mock_request, SessionAutoComponent())
    context = call_context(component, 'noop')
    reconstructed = SessionAutoComponent.from_attribute_call_resolver_context(context)
    reconstructed.process_attribute_call(context)

    assert written == []


def test_failed_call_does_not_flush(mock_request: HttpRequest) -> None:
    component = Glue.object(mock_request, SessionFailComponent())
    context = call_context(component, 'explode')
    reconstructed = SessionFailComponent.from_attribute_call_resolver_context(context)

    with pytest.raises(ValueError, match='boom'):
        reconstructed.process_attribute_call(context)

    assert 'lost' not in ComponentSession(mock_request, 'SessionFailComponent')
