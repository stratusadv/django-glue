from __future__ import annotations

from itertools import count
from typing import TYPE_CHECKING, Any

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission

from django_glue import Glue, get_model_access
from django_glue.glue.policy import GluePolicy
from django_glue.tests.glue.test_callable_parameters import call_context
from test_project.fight.models import Fight
from test_project.gorilla.models import Gorilla

if TYPE_CHECKING:
    from django.contrib.auth.models import User
    from django.db.models import Model
    from django.http import HttpRequest


pytestmark = pytest.mark.django_db

_user_numbers = count()


def _user_with(*codenames: str, model: type[Model] = Gorilla, **fields: Any) -> User:
    user = get_user_model().objects.create_user(
        username=f'model.access.{next(_user_numbers)}',
        **fields,
    )
    user.user_permissions.add(
        *Permission.objects.filter(
            codename__in=codenames,
            content_type__app_label=model._meta.app_label,
        )
    )

    # A fresh instance, so the permissions are not read from a cache filled before they were added.
    return get_user_model().objects.get(pk=user.pk)


class GorillaAccessComponent(Glue.ModelAccessMixin, Glue.Component):
    template = 'glue_template_test.html'

    def get_permission_model(self) -> type[Model]:
        return Gorilla


class RaisedAccessComponent(GorillaAccessComponent):
    def __post_init__(self, request: HttpRequest) -> None:
        super().__post_init__(request)

        self.access = Glue.Access.DELETE


class FightAccessComponent(GorillaAccessComponent):
    def get_permission_model(self) -> type[Model]:
        return Fight


class MissingModelComponent(Glue.ModelAccessMixin, Glue.Component):
    template = 'glue_template_test.html'


class FightComponent(Glue.Component):
    template = 'glue_template_test.html'

    def get_permission_model(self) -> type[Model]:
        return Fight


class MixedInFightComponent(Glue.ModelAccessMixin, FightComponent):
    pass


class AttributeGorillaComponent(Glue.ModelAccessMixin, Glue.Component):
    template = 'glue_template_test.html'
    permission_model = Gorilla


class AttributeOverMethodComponent(Glue.ModelAccessMixin, FightComponent):
    permission_model = Gorilla


class MethodOverAttributeComponent(AttributeGorillaComponent):
    def get_permission_model(self) -> type[Model]:
        return Fight


class ViewOnlyProducerComponent(Glue.Component):
    template = 'glue_template_test.html'

    @Glue.attr
    def spawn(self) -> GorillaAccessComponent:
        return GorillaAccessComponent()


def test_get_model_access_is_none_without_the_view_permission() -> None:
    assert get_model_access(AnonymousUser(), Gorilla) is None
    assert get_model_access(_user_with('delete_gorilla'), Gorilla) is None


def test_get_model_access_is_the_highest_level_held_with_every_level_below_it() -> None:
    assert get_model_access(_user_with('view_gorilla'), Gorilla) is Glue.Access.VIEW
    assert get_model_access(_user_with('view_gorilla', 'add_gorilla'), Gorilla) is Glue.Access.ADD

    every_permission = ('view_gorilla', 'add_gorilla', 'change_gorilla', 'delete_gorilla')
    assert get_model_access(_user_with(*every_permission), Gorilla) is Glue.Access.DELETE


def test_get_model_access_grants_nothing_above_a_missing_level() -> None:
    user = _user_with('view_gorilla', 'change_gorilla', 'delete_gorilla')

    assert get_model_access(user, Gorilla) is Glue.Access.VIEW


def test_get_model_access_gives_a_superuser_every_level() -> None:
    superuser = _user_with(is_superuser=True)

    assert get_model_access(superuser, Gorilla) is Glue.Access.DELETE


def test_mixin_signs_the_access_the_user_holds_on_the_model(mock_request: HttpRequest) -> None:
    mock_request.user = _user_with('view_gorilla', 'add_gorilla', 'change_gorilla')

    component = Glue.object(mock_request, GorillaAccessComponent())

    assert component.access is Glue.Access.CHANGE
    assert component.policy.access is Glue.Access.CHANGE


def test_mixin_keeps_the_given_access_without_the_view_permission(
    mock_request: HttpRequest,
) -> None:
    mock_request.user = _user_with('change_gorilla')

    component = Glue.object(mock_request, GorillaAccessComponent(access=Glue.Access.CHANGE))

    assert component.policy.access is Glue.Access.CHANGE


def test_subclass_access_is_signed_for_a_user_without_the_view_permission(
    mock_request: HttpRequest,
) -> None:
    mock_request.user = AnonymousUser()

    component = Glue.object(mock_request, RaisedAccessComponent())

    assert component.policy.access is Glue.Access.DELETE


def test_mixin_reads_the_permissions_of_the_model_a_subclass_names(
    mock_request: HttpRequest,
) -> None:
    mock_request.user = _user_with('view_fight', 'add_fight', model=Fight)

    component = Glue.object(mock_request, FightAccessComponent())

    assert component.policy.access is Glue.Access.ADD


def test_access_a_subclass_assigns_after_the_mixin_is_the_access_signed(
    mock_request: HttpRequest,
) -> None:
    mock_request.user = _user_with('view_gorilla')

    component = Glue.object(mock_request, RaisedAccessComponent())

    assert component.policy.access is Glue.Access.DELETE


def test_mixin_listed_first_uses_the_model_its_base_component_names(
    mock_request: HttpRequest,
) -> None:
    mock_request.user = _user_with('view_fight', model=Fight)

    component = Glue.object(mock_request, MixedInFightComponent())

    assert component.policy.access is Glue.Access.VIEW


def test_mixin_reads_a_permission_model_attribute(mock_request: HttpRequest) -> None:
    mock_request.user = _user_with('view_gorilla', 'add_gorilla')

    component = Glue.object(mock_request, AttributeGorillaComponent())

    assert component.policy.access is Glue.Access.ADD


def test_a_subclass_attribute_overrides_its_base_components_method(
    mock_request: HttpRequest,
) -> None:
    mock_request.user = _user_with('view_gorilla', 'add_gorilla')

    component = Glue.object(mock_request, AttributeOverMethodComponent())

    assert component.policy.access is Glue.Access.ADD


def test_a_subclass_method_overrides_its_base_components_attribute(
    mock_request: HttpRequest,
) -> None:
    mock_request.user = _user_with('view_fight', 'add_fight', 'change_fight', model=Fight)

    component = Glue.object(mock_request, MethodOverAttributeComponent())

    assert component.policy.access is Glue.Access.CHANGE


def test_mixin_without_a_permission_model_names_both_ways_to_give_one(
    mock_request: HttpRequest,
) -> None:
    mock_request.user = _user_with('view_gorilla')

    with pytest.raises(NotImplementedError, match='must set permission_model or implement'):
        Glue.object(mock_request, MissingModelComponent())


def test_a_returned_component_is_capped_at_the_access_of_its_producer(
    mock_request: HttpRequest,
) -> None:
    every_permission = ('view_gorilla', 'add_gorilla', 'change_gorilla', 'delete_gorilla')
    mock_request.user = _user_with(*every_permission)

    producer = Glue.object(mock_request, ViewOnlyProducerComponent())
    context = call_context(producer, 'spawn')
    reconstructed = ViewOnlyProducerComponent.from_attribute_call_resolver_context(context)
    entry, introduced = reconstructed.process_attribute_call(context)
    spawned = next(item for item in introduced if item['address'] == entry['result'])

    assert GluePolicy.from_token(spawned['policy_token']).access is Glue.Access.VIEW
