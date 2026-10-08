from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest
from django.contrib.sessions.backends.cache import SessionStore

from django_glue import Glue
from django_glue.conf import settings
from django_glue.exceptions import GlueComponentParameterError
from django_glue.glue.attributes.definition import GlueValueRole
from django_glue.glue.base import BaseGlue
from django_glue.glue.components import Component
from django_glue.glue.components.session import ComponentSession
from django_glue.tests.glue.test_callable_parameters import call_context

if TYPE_CHECKING:
    from django.http import HttpRequest
    from django.test import RequestFactory

CORRUPT_KEY = f'{settings.DJANGO_GLUE_COMPONENT_SESSION_KEY_PREFIX}corrupt'


def stored(request: HttpRequest, component_class: type[Component]) -> ComponentSession:
    """The session entry a component class reads and writes, opened without a component."""
    namespace = f'{component_class.__module__}.{component_class.__qualname__}'
    return ComponentSession(request.session, namespace)


@pytest.fixture
def mock_request(request_factory: RequestFactory) -> HttpRequest:
    """
    A request carrying a real session store, so these tests exercise Django's
    own modified tracking. The shared MockSession is a plain dict whose
    writes never mark it modified.
    """
    request = request_factory.get('/')
    request.session = SessionStore()
    request.session.create()
    request.session.modified = False
    return request


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


class SessionPostInitComponent(Component):
    template = 'glue_template_test.html'

    def __post_init__(self, request: HttpRequest) -> None:
        self.session['mounted'] = True


class SessionAttrComponent(Component):
    template = 'glue_template_test.html'

    step: int = Glue.SessionAttr(0)
    seen: list[int] = Glue.SessionAttr(default_factory=list)

    @Glue.attr
    def advance(self) -> None:
        self.step += 1

    count: int = Glue.attr(0, editable=True)

    @Glue.attr(skip_rerender=True)
    def advance_quietly(self) -> None:
        self.step += 1

    @Glue.attr(skip_rerender=True)
    def advance_through_the_mapping(self) -> None:
        self.session['step'] = self.step + 1

    @Glue.attr(skip_rerender=True)
    def reset_quietly(self) -> None:
        del self.step

    @Glue.attr(skip_rerender=True)
    def write_other_keys(self) -> None:
        self.session['undeclared'] = 1
        self.session['count'] = 5

    @Glue.attr(skip_rerender=True)
    def read_quietly(self) -> int:
        return self.step


class SessionSecretComponent(Component):
    template = 'glue_template_test.html'

    def __post_init__(self, request: HttpRequest) -> None:
        self.session['session-secret-mounted'] = 'session-secret-value'

    @Glue.attr
    def record(self) -> None:
        self.session['session-secret-recorded'] = 'session-secret-value'


class SessionFailComponent(Component):
    template = 'glue_template_test.html'

    @Glue.attr
    def explode(self) -> None:
        self.session['lost'] = 'value'
        msg = 'boom'
        raise ValueError(msg)


def test_fresh_namespace_loads_empty(mock_request: HttpRequest) -> None:
    session = ComponentSession(mock_request.session, 'fresh')

    assert len(session) == 0
    assert 'nope' not in session
    assert session.get('nope') is None


def test_set_round_trips_into_a_second_session(mock_request: HttpRequest) -> None:
    first = ComponentSession(mock_request.session, 'round_trip')
    first['count'] = 1
    first['name'] = 'nathan'

    second = ComponentSession(mock_request.session, 'round_trip')

    assert dict(second) == {'count': 1, 'name': 'nathan'}
    assert second['count'] == 1


def test_reading_a_clean_namespace_leaves_the_session_unmodified(mock_request: HttpRequest) -> None:
    session = ComponentSession(mock_request.session, 'clean')

    assert 'nope' not in session
    assert session.get('nope') is None
    assert mock_request.session.modified is False


def test_mutation_marks_the_session_modified(mock_request: HttpRequest) -> None:
    session = ComponentSession(mock_request.session, 'once')

    assert mock_request.session.modified is False
    session['a'] = 1

    assert mock_request.session.modified is True


def test_setting_the_same_value_marks_modified(mock_request: HttpRequest) -> None:
    session = ComponentSession(mock_request.session, 'same')
    session['count'] = 1
    mock_request.session.modified = False

    session['count'] = 1

    assert mock_request.session.modified is True


def test_assigning_back_a_value_mutated_in_place_marks_modified(mock_request: HttpRequest) -> None:
    session = ComponentSession(mock_request.session, 'mutated')
    session['items'] = []
    mock_request.session.modified = False

    items = session['items']
    items.append(1)
    session['items'] = items

    assert mock_request.session.modified is True
    assert ComponentSession(mock_request.session, 'mutated')['items'] == [1]


def test_overwriting_with_a_different_value_marks_modified(mock_request: HttpRequest) -> None:
    session = ComponentSession(mock_request.session, 'overwrite')
    session['count'] = 1
    mock_request.session.modified = False

    session['count'] = 2

    assert mock_request.session.modified is True


def test_delete_marks_modified_and_persists(mock_request: HttpRequest) -> None:
    first = ComponentSession(mock_request.session, 'delete')
    first['a'] = 1
    first['b'] = 2

    second = ComponentSession(mock_request.session, 'delete')
    del second['a']

    third = ComponentSession(mock_request.session, 'delete')

    assert dict(third) == {'b': 2}
    assert mock_request.session.modified is True


def test_namespaces_are_isolated(mock_request: HttpRequest) -> None:
    alpha = ComponentSession(mock_request.session, 'alpha')
    beta = ComponentSession(mock_request.session, 'beta')
    alpha['shared'] = 'alpha'
    beta['shared'] = 'beta'

    assert ComponentSession(mock_request.session, 'alpha')['shared'] == 'alpha'
    assert ComponentSession(mock_request.session, 'beta')['shared'] == 'beta'


def test_non_string_keys_raise_type_error(mock_request: HttpRequest) -> None:
    session = ComponentSession(mock_request.session, 'keys')

    with pytest.raises(TypeError):
        session[1] = 'x'  # type: ignore[index]
    with pytest.raises(TypeError):
        del session[1]  # type: ignore[index]
    assert len(session) == 0


def test_stored_value_that_is_not_a_dict_loads_empty(mock_request: HttpRequest) -> None:
    session = ComponentSession(mock_request.session, 'corrupt')
    mock_request.session[CORRUPT_KEY] = 'not-a-dict'
    mock_request.session.modified = False

    assert len(session) == 0
    assert mock_request.session[CORRUPT_KEY] == 'not-a-dict'
    assert mock_request.session.modified is False


def test_write_replaces_a_stored_value_that_is_not_a_dict(mock_request: HttpRequest) -> None:
    session = ComponentSession(mock_request.session, 'corrupt')
    mock_request.session[CORRUPT_KEY] = 'not-a-dict'
    mock_request.session.modified = False

    session['count'] = 1

    assert mock_request.session[CORRUPT_KEY] == {'count': 1}
    assert mock_request.session.modified is True


def test_component_session_uses_the_class_qualname(mock_request: HttpRequest) -> None:
    component = Glue.object(mock_request, SessionProbeComponent())

    component.session['last'] = 'written'

    assert component.session is component.session
    assert stored(mock_request, SessionProbeComponent)['last'] == 'written'


def test_same_named_classes_in_different_modules_keep_separate_entries(
    mock_request: HttpRequest,
) -> None:
    billing, reports = (
        type(
            'SessionTwinComponent',
            (Component,),
            {'__module__': module, 'template': 'glue_template_test.html'},
        )
        for module in ('billing.components', 'reports.components')
    )

    Glue.object(mock_request, billing()).session['step'] = 'billing'
    Glue.object(mock_request, reports()).session['step'] = 'reports'

    assert Glue.object(mock_request, billing()).session['step'] == 'billing'
    assert Glue.object(mock_request, reports()).session['step'] == 'reports'


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


def test_post_init_write_is_visible_on_introduction(mock_request: HttpRequest) -> None:
    Glue.object(mock_request, SessionPostInitComponent())

    assert stored(mock_request, SessionPostInitComponent)['mounted'] is True


def test_callable_write_reaches_the_session(mock_request: HttpRequest) -> None:
    component = Glue.object(mock_request, SessionAutoComponent())
    context = call_context(component, 'record')
    reconstructed = SessionAutoComponent.from_attribute_call_resolver_context(context)
    reconstructed.process_attribute_call(context)

    assert stored(mock_request, SessionAutoComponent)['auto'] == 'recorded'


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

    assert stored(mock_request, SessionFailComponent)['lost'] == 'value'


def test_mapping_writes_never_reach_the_token_or_the_response(mock_request: HttpRequest) -> None:
    component = Glue.object(mock_request, SessionSecretComponent())
    context = call_context(component, 'record')
    reconstructed = SessionSecretComponent.from_attribute_call_resolver_context(context)
    entry, introduced = reconstructed.process_attribute_call(context)

    sent = json.dumps(
        [
            component.policy.model_dump(mode='json'),
            component.entry.model_dump(mode='json'),
            reconstructed.policy.model_dump(mode='json'),
            entry,
            introduced,
        ],
        default=str,
    )

    assert dict(stored(mock_request, SessionSecretComponent)) == {
        'session-secret-mounted': 'session-secret-value',
        'session-secret-recorded': 'session-secret-value',
    }
    assert 'html' in entry
    assert 'session-secret' not in sent


def call_entry(component: Component, attribute: str) -> dict[str, Any]:
    context = call_context(component, attribute)
    reconstructed = type(component).from_attribute_call_resolver_context(context)
    entry, _introduced = reconstructed.process_attribute_call(context)
    return entry


def test_session_attr_default_read_leaves_the_session_clean(mock_request: HttpRequest) -> None:
    component = Glue.object(mock_request, SessionAttrComponent())

    assert component.step == 0
    assert component.seen == []
    assert mock_request.session.modified is False
    assert len(component.session) == 0


def test_reading_a_mutable_session_attr_default_returns_a_copy(mock_request: HttpRequest) -> None:
    component = Glue.object(mock_request, SessionAttrComponent())

    component.seen.append(1)

    assert component.seen == []


def test_session_attr_reaches_the_client_but_not_the_token(mock_request: HttpRequest) -> None:
    component = Glue.object(mock_request, SessionAttrComponent())
    fields = component.get_static_data()['fields']

    assert component.get_computed_data(include_all=True) == {'seen': [], 'step': 0}
    assert fields['step'] == {'value_path': 'step', 'editable': False}
    assert component.policy.state_snapshot == {'count': 0}


def test_session_attr_assignment_is_stored_under_its_name(mock_request: HttpRequest) -> None:
    component = Glue.object(mock_request, SessionAttrComponent())

    component.step = 3

    assert mock_request.session.modified is True
    assert dict(stored(mock_request, SessionAttrComponent)) == {'step': 3}


def test_callable_response_carries_the_session_attr_it_changed(mock_request: HttpRequest) -> None:
    component = Glue.object(mock_request, SessionAttrComponent())

    entry = call_entry(component, 'advance')

    assert entry['computed_data'] == {'seen': [], 'step': 1}


@pytest.mark.parametrize('callable_name', ['advance_quietly', 'advance_through_the_mapping'])
def test_skip_rerender_callable_sends_the_session_attr_it_wrote(
    mock_request: HttpRequest, callable_name: str
) -> None:
    component = Glue.object(mock_request, SessionAttrComponent())

    entry = call_entry(component, callable_name)

    assert entry['computed_data'] == {'step': 1}
    assert 'html' not in entry
    assert stored(mock_request, SessionAttrComponent)['step'] == 1


def test_skip_rerender_callable_sends_the_default_of_a_deleted_session_attr(
    mock_request: HttpRequest,
) -> None:
    component = Glue.object(mock_request, SessionAttrComponent())
    component.step = 3

    entry = call_entry(component, 'reset_quietly')

    assert entry['computed_data'] == {'step': 0}


def test_skip_rerender_callable_sends_nothing_for_other_session_keys(
    mock_request: HttpRequest,
) -> None:
    component = Glue.object(mock_request, SessionAttrComponent())

    entry = call_entry(component, 'write_other_keys')

    assert 'computed_data' not in entry


def test_skip_rerender_callable_that_only_reads_sends_nothing(mock_request: HttpRequest) -> None:
    component = Glue.object(mock_request, SessionAttrComponent())

    entry = call_entry(component, 'read_quietly')

    assert entry['result'] == 0
    assert 'computed_data' not in entry


def test_on_write_receives_each_key_set_or_deleted(mock_request: HttpRequest) -> None:
    written: list[str] = []
    session = ComponentSession(mock_request.session, 'observed', on_write=written.append)

    session['a'] = 1
    _ = session['a']
    del session['a']

    assert written == ['a', 'a']


def test_session_attr_survives_to_a_second_request(
    mock_request: HttpRequest, request_factory: RequestFactory
) -> None:
    call_entry(Glue.object(mock_request, SessionAttrComponent()), 'advance')

    second_request = request_factory.get('/')
    second_request.session = mock_request.session
    fresh = Glue.object(second_request, SessionAttrComponent())

    assert fresh.step == 1


def test_session_writes_survive_a_save_and_reload(
    mock_request: HttpRequest, request_factory: RequestFactory
) -> None:
    component = Glue.object(mock_request, SessionAttrComponent())
    call_entry(component, 'advance')
    component.session['note'] = ['kept']

    # SessionMiddleware saves only a session a request marked modified.
    assert mock_request.session.modified is True
    mock_request.session.save()

    second_request = request_factory.get('/')
    second_request.session = SessionStore(session_key=mock_request.session.session_key)
    fresh = Glue.object(second_request, SessionAttrComponent())

    assert second_request.session is not mock_request.session
    assert fresh.step == 1
    assert fresh.session['note'] == ['kept']


def test_deleting_a_session_attr_restores_its_default(mock_request: HttpRequest) -> None:
    component = Glue.object(mock_request, SessionAttrComponent())
    component.step = 3

    del component.step

    assert component.step == 0
    assert 'step' not in component.session


def test_session_attr_requires_a_bound_component() -> None:
    component = SessionAttrComponent()

    with pytest.raises(RuntimeError, match='unbound component'):
        _ = component.step


def test_session_attr_is_not_a_construction_parameter() -> None:
    with pytest.raises(GlueComponentParameterError, match='Unknown parameters'):
        SessionAttrComponent(step=3)


def test_session_attr_shortcut_matches_glue_attr_session() -> None:
    assert Glue.SessionAttr(0).__glue_options__ == Glue.attr(0, session=True).__glue_options__
    assert Glue.SessionAttr(0).__glue_options__.value_role is GlueValueRole.DERIVED_OUTPUT


@pytest.mark.parametrize(
    'option',
    [
        {'parameter': True},
        {'editable': True},
        {'render_as_html': True},
        {'skip_rerender': True},
        {'glue_factory': dict},
    ],
)
def test_session_attr_rejects_options_that_do_not_apply(option: dict[str, Any]) -> None:
    with pytest.raises(TypeError, match=f'cannot be combined with {next(iter(option))}'):
        Glue.SessionAttr(0, **option)


def test_session_attr_rejects_a_method_or_property() -> None:
    def method(self: Component) -> None:
        pass

    with pytest.raises(TypeError, match='only valid for value declarations'):
        Glue.attr(session=True)(method)
    with pytest.raises(TypeError, match='only valid for value declarations'):
        Glue.attr(method, session=True)
    with pytest.raises(TypeError, match='only valid for value declarations'):
        Glue.attr(property(method), session=True)


def test_session_attr_on_a_non_component_raises() -> None:
    with pytest.raises(RuntimeError) as raised:

        class NonComponentSessionGlue(BaseGlue):
            namespace = 'nonComponentSession'
            step = Glue.SessionAttr(0)

    assert isinstance(raised.value.__cause__, TypeError)
    assert 'is not a Component' in str(raised.value.__cause__)
