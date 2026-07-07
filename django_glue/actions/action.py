import inspect
from typing import Any, Callable

from pydantic import BaseModel

from django_glue.access.access import GlueAccess
from django_glue.actions.decorators import GLUE_ACTIONS
from django_glue.proxies.proxy import BaseGlueProxy
from django_glue.utils import get_attr_from_path_string


class GlueAction(BaseModel):
    name: str
    parameters: dict[str, str | None]
    required_access: GlueAccess
    target_class_path: str
    provider_class_path: str
    client_proxy_access_path: str = ''
    provider_factory: Callable | None = None

    @property
    def target_class(self) -> type:
        target_class = get_attr_from_path_string(self.target_class_path)
        if not isinstance(target_class, type):
            raise ValueError('target_class_path for instance does not refer to a valid class.')

        return target_class

    @property
    def provider_class(self) -> type:
        provider_class = get_attr_from_path_string(self.provider_class_path)
        if not isinstance(provider_class, type):
            raise ValueError('target_class_path for instance does not refer to a valid class.')

        return provider_class

    @property
    def callable(self) -> Callable:
        target_class = self.target_class

        if self.provider_class is not None:
            action_function = getattr(self.provider_class, self.name, None)
        else:
            action_function = getattr(self.target_class, self.name, None)

        if not action_function or not isinstance(action_function, Callable):
            raise ValueError(f'Could not find valid callable named {self.name} on action target class {target_class.__name__}')

        return action_function


def register_target_actions(target: Any) -> None:
    if isinstance(target, BaseGlueProxy):
        register_action_provider(
            action_provider_class=target.__class__,
            target_class=target.__class__,
        )

    glue_options = getattr(target, 'GlueMeta', None)
    if glue_options:
        for action_provider_class, action_provider_config in getattr(
            glue_options,
            'action_providers', None
        ) or []:
            if action_provider_class.__name__ not in GLUE_ACTIONS:
                register_action_provider(
                    action_provider_class=action_provider_class,
                    target_class=target.__class__,
                    # TODO: validate this structure
                    client_proxy_access_path=action_provider_config['client_proxy_access_path'],
                    provider_factory=action_provider_config['provider_factory']
                )


def register_action_provider(
        action_provider_class: type,
        target_class: type,
        client_proxy_access_path: str = '',
        provider_factory: Callable | None = None
    ) -> None:
    if action_provider_class.__name__ not in GLUE_ACTIONS:
        for function_name, function in inspect.getmembers(action_provider_class):
            key_name = f'{action_provider_class.__name__}.{function_name}'

            if key_name in GLUE_ACTIONS:
                continue

            required_access = getattr(function, '__required_glue_access__', None)
            if required_access is None:
                continue

            signature = inspect.signature(inspect.unwrap(function))
            parameters = signature.parameters
            name = function_name
            parameter_data: dict[str, str | None] = {}

            for param_name, param_value in list(parameters.items())[2:]:
                # Convert annotation to string for JSON serialization
                annotation = param_value.annotation
                if annotation is inspect.Parameter.empty:
                    parameter_data[param_name] = None
                elif isinstance(annotation, type):
                    parameter_data[param_name] = annotation.__name__
                else:
                    parameter_data[param_name] = str(annotation)

            GLUE_ACTIONS.update({
                key_name: GlueAction(
                    name=name,
                    parameters=parameter_data,
                    required_access=required_access,
                    target_class_path=f'{target_class.__module__}.{target_class.__name__}',
                    provider_class_path=f'{action_provider_class.__module__}.{action_provider_class.__name__}',
                    client_proxy_access_path=client_proxy_access_path,
                    provider_factory=provider_factory
                ),
            })


# Resolve forward references in GlueProxyContract now that GlueAction is defined
from django_glue.proxies.contract import GlueProxyContract
GlueProxyContract.model_rebuild()
