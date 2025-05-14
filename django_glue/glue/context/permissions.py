from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from django.contrib.auth import User


def create_permission_checker(user: User) -> Callable[[Any, str], bool]:
    def check_permission(instance: Any, permission_type: str = 'view') -> bool:
        if not hasattr(instance, '_meta'):
            return True

        app_label: str = instance._meta.app_label
        model_name: str = instance._meta.model_name

        permission: str = f'{app_label}.{permission_type}_{model_name}'

        return user.has_perm(permission)

    return check_permission
