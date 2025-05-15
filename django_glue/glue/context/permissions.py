from __future__ import annotations

from turtle import back
from typing import Any, TYPE_CHECKING

from django.db.models import Model

if TYPE_CHECKING:
    from django.contrib.auth.models import User


class PermissionBackend:
    def __init__(self, user: User = None) -> None:
        self.user = user

    def has_permission(self, obj_or_model: Model | type[Model], permission_type: str, context: dict[str, Any] | None = None) -> bool | None:
        message = 'Subclasses must implement has_permission'
        raise NotImplementedError(message)

    def filter_permitted_fields(self, obj, fields, perm_type="view"):
        if hasattr(self, "has_field_permission"):
            return {
                f for f in fields
                if self.has_field_permission(obj, f, perm_type)
            }
        return fields


class DjangoModelPermissionBackend(PermissionBackend):
    def has_permission(self, obj_or_model: Model | type[Model], permission_type: str, context: dict[str, Any] | None = None) -> bool:
        if not self.user or not self.user.is_authenticated:
            return False

        if isinstance(obj_or_model, type):
            model_cls = obj_or_model
        else:
            model_cls = obj_or_model.__class__

        if not hasattr(model_cls, '_meta'):
            return True

        app_label = model_cls._meta.app_label
        model_name = model_cls._meta.model_name

        permission = f'{app_label}.{permission_type}_{model_name}'
        return self.user.has_perm(permission)


class ObjectLevelPermissionBackend(PermissionBackend):
    def has_permission(self, obj_or_model: Model | type[Model], permission_type: str, context: dict[str, Any] | None = None) -> bool | None:
        if not self.user or not self.user.is_authenticated:
            return False

        if isinstance(obj_or_model, type):
            return True

        method_name = f'has_{permission_type}_permission'

        if hasattr(obj_or_model, method_name):
            method = getattr(obj_or_model, method_name)

            if callable(method):
                return method(self.user)

        if hasattr(obj_or_model, 'has_permission'):
            return obj_or_model.has_permission(self.user, permission_type)

        return None


class FieldLevelPermissionBackend(PermissionBackend):
    def has_permission(self, _obj_or_model: Model | type[Model], _permission_type: str, _context: dict[str, Any] | None = None) -> bool:
        return True

    def has_field_permission(self, obj: Model, field_name: str, permission_type: str) -> bool:
        if not self.user or not self.user.is_authenticated:
            return False

        method_name = f'has_{field_name}_{permission_type}_permission'

        if hasattr(obj, method_name):
            method = getattr(obj, method_name)

            if callable(method):
                return method(self.user)

        if hasattr(obj, 'get_field_permissions'):
            perms = obj.get_field_permissions(self.user)
            field_key = f'{field_name}.{permission_type}'
            return field_key in perms or f'*.{permission_type}' in perms

        return True

    def filter_permitted_fields(self, obj: Model, fields: set[str], permission_type: str) -> set[str]:
        if not self.user or not self.user.is_authenticated:
            return set()

        if hasattr(obj, 'get_permitted_fields'):
            return obj.get_permitted_fields(self.user, permission_type)

        return {f for f in fields if self.has_field_permission(obj, f, permission_type)}


class RoleBasedPermissionBackend(PermissionBackend):
    def has_permission(self, obj_or_model: Model | type[Model], permission_type: str, context: dict[str, Any] | None = None) -> bool:
        if not self.user or not self.user.is_authenticated:
            return False

        user_roles = self._get_user_roles()

        if isinstance(obj_or_model, type):
            model_cls = obj_or_model
            obj_id = None
        else:
            model_cls = obj_or_model.__class__
            obj_id = obj_or_model.pk

        for role in user_roles:
            if self._role_has_permission(role, model_cls, obj_id, permission_type):
                return True

        return False

    def _get_user_roles(self) -> list[Any]:
        if hasattr(self.user, 'get_roles'):
            return self.user.get_roles()

        return getattr(self.user, 'roles', [])

    def _role_has_permission(self, _role: Any, _model_cls: type[Model], _obj_id: Any, _permission_type: str) -> bool:
        return False


class PermissionChecker:
    def __init__(self, user: User | None = None) -> None:
        self.user = user
        self.backends: list[PermissionBackend] = []
        self.cache: dict[str, bool] = {}

        if user:
            self.register_backend(DjangoModelPermissionBackend(user))
            self.register_backend(ObjectLevelPermissionBackend(user))

    def register_backend(self, backend: PermissionBackend) -> None:
        self.backends.append(backend)

    def check_permission(
        self,
        obj_or_model: Model | type[Model],
        permission_type: str = 'view',
        context: dict[str, Any] | None = None
    ) -> bool:
        if self.user and self.user.is_superuser:
            return True

        # cache_key = self._get_cache_key(obj_or_model, permission_type, context)

        # if cache_key in self.cache:
        #     return self.cache[cache_key]

        deferred = False

        for backend in self.backends:
            result = backend.has_permission(obj_or_model, permission_type, context)

            # If the backend returns True, permission is granted
            if result is True:
                # self.cache[cache_key] = True
                return True

            if result is None:
                deferred = True

        if not deferred:
            # self.cache[cache_key] = False
            return False

        if isinstance(obj_or_model, Model):
            django_backend = DjangoModelPermissionBackend(self.user)
            result = django_backend.has_permission(obj_or_model, permission_type, context)

            # self.cache[cache_key] = result
            return result

        # self.cache[cache_key] = True
        return True

    def _get_cache_key(self, obj_or_model: Model | type[Model], permission_type: str, context: dict[str, Any] | None) -> str:
        if isinstance(obj_or_model, Model):
            obj_id = getattr(obj_or_model, 'pk', id(obj_or_model))
            model_key = f'{obj_or_model.__class__.__name__}:{obj_id}'
        else:
            model_key = obj_or_model.__name__

        context_key = ''

        if context:
            context_key = ':'.join(f'{k}={v}' for k, v in sorted(context.items()))

        return f'{model_key}:{permission_type}:{context_key}'

    def check_field_permission(
        self,
        obj: Model,
        field_name: str,
        permission_type: str = 'view'
    ) -> bool:
        if not self.check_permission(obj, permission_type):
            return False

        for backend in self.backends:
            if hasattr(backend, 'has_field_permission'):
                if not backend.has_field_permission(obj, field_name, permission_type):
                    return False

        return True

    def get_permitted_fields(
        self,
        obj: Model,
        permission_type: str = 'view'
    ) -> set[str]:
        fields = {
            field.name
            for field in obj._meta.get_fields()
        }

        if not self.check_permission(obj, permission_type):
            return set()

        permitted = set(fields)

        for backend in self.backends:
            if hasattr(backend, 'filter_permitted_fields'):
                permitted = backend.filter_permitted_fields(obj, permitted, permission_type)

        return permitted


def create_permission_checker(
    user: User | None = None,
    backends: list[str] | None = None,
    **options
) -> PermissionChecker:
    checker = PermissionChecker(user)

    if not backends:
        checker.register_backend(DjangoModelPermissionBackend(user))
        checker.register_backend(ObjectLevelPermissionBackend(user))

        if options.get('field_level', False):
            checker.register_backend(FieldLevelPermissionBackend(user))

        if options.get('role_based', False):
            checker.register_backend(RoleBasedPermissionBackend(user))
    else:
        mapping = {
            'django': DjangoModelPermissionBackend,
            'object': ObjectLevelPermissionBackend,
            'field': FieldLevelPermissionBackend,
            'role': RoleBasedPermissionBackend,
        }

        for name in backends:
            if name in mapping:
                checker.register_backend(mapping[name](user))

    if 'custom_backend' in options:
        for backend_cls in options['custom_backend']:
            checker.register_backend(backend_cls(user))

    return checker
