from __future__ import annotations

import datetime
import decimal
import json
import uuid

from enum import Enum
from typing import Any, Callable, TYPE_CHECKING

from django.core.paginator import Page
from django.db.models import Model, QuerySet
from django.forms.models import model_to_dict
from django.http import QueryDict

if TYPE_CHECKING:
    from django.contrib.auth.models import User


class TypeSerializer:
    def can_serialize(self, data: Any, context: dict[str, Any]) -> bool:
        message = 'Subclasses must implement can_serialize'
        raise NotImplementedError(message)

    def serialize(self, data: Any, context: dict[str, Any]) -> Any:
        message = 'Subclasses must implement serialize'
        raise NotImplementedError(message)


class NoneSerializer(TypeSerializer):
    def can_serialize(self, data: Any, _context: dict[str, Any]) -> bool:
        return data is None

    def serialize(self, _data: Any, _context: dict[str, Any]) -> Any:
        return None


class PrimitiveSerializer(TypeSerializer):
    def can_serialize(self, data: Any, _context: dict[str, Any]) -> bool:
        return isinstance(data, str | int | float | bool)

    def serialize(self, data: Any, context: dict[str, Any]) -> Any:
        if isinstance(data, str) and context['serializer']._is_json(data):
            try:
                parsed = json.loads(data)

                if context['serializer']._is_choices_list(parsed):
                    return dict(parsed)

                return context['serializer'].serialize(
                    parsed,
                    context.get('user'),
                    context.get('permission_checker'),
                    context['exclude'],
                    context['max_depth'] - 1
                )
            except (json.JSONDecodeError, ValueError):
                pass

        return data


class DateTimeSerializer(TypeSerializer):
    def can_serialize(self, data: Any, _context: dict[str, Any]) -> bool:
        return isinstance(data, datetime.datetime | datetime.date | datetime.time)

    def serialize(self, data: Any, _context: dict[str, Any]) -> Any:
        return data.isoformat()


class DecimalSerializer(TypeSerializer):
    def can_serialize(self, data: Any, _context: dict[str, Any]) -> bool:
        return isinstance(data, decimal.Decimal)

    def serialize(self, data: Any, _context: dict[str, Any]) -> Any:
        return float(data)


class UUIDSerializer(TypeSerializer):
    def can_serialize(self, data: Any, _context: dict[str, Any]) -> bool:
        return isinstance(data, uuid.UUID)

    def serialize(self, data: Any, _context: dict[str, Any]) -> Any:
        return str(data)


class EnumSerializer(TypeSerializer):
    def can_serialize(self, data: Any, _context: dict[str, Any]) -> bool:
        return isinstance(data, Enum)

    def serialize(self, data: Any, _context: dict[str, Any]) -> Any:
        return data.value


class ChoicesSerializer(TypeSerializer):
    def can_serialize(self, data: Any, context: dict[str, Any]) -> bool:
        return context['serializer']._is_choices_list(data)

    def serialize(self, data: Any, _context: dict[str, Any]) -> Any:
        return dict(data)


class ModelSerializer(TypeSerializer):
    def can_serialize(self, data: Any, _context: dict[str, Any]) -> bool:
        return isinstance(data, Model)

    def serialize(self, data: Any, context: dict[str, Any]) -> Any:
        if context.get('permission_checker') and not context['permission_checker'](data):
            return {'pk': data.pk, '__str__': str(data)}

        model_dict = model_to_dict(data)
        model_dict['pk'] = data.pk
        model_dict['__str__'] = str(data)

        for field in data._meta.fields:
            if field.choices and hasattr(data, f'get_{field.name}_display'):
                display_method = getattr(data, f'get_{field.name}_display')
                model_dict[f'{field.name}_display'] = display_method()

            if field.is_relation and field.name not in model_dict:
                related_obj = getattr(data, field.name, None)

                if related_obj is not None:
                    model_dict[field.name] = related_obj

        for attr_name, attr_value in data.__dict__.items():
            if attr_name in model_dict or attr_name.startswith('_'):
                continue

            if attr_name in ('_state', '_prefetched_objects_cache'):
                continue

            model_dict[attr_name] = attr_value

        excluded_keys = context['exclude']

        for key in list(model_dict.keys()):
            if key in excluded_keys:
                del model_dict[key]

        return context['serializer'].serialize(
            model_dict,
            context.get('user'),
            context.get('permission_checker'),
            context['exclude'],
            context['max_depth'] - 1
        )


class QuerySetSerializer(TypeSerializer):
    def can_serialize(self, data: Any, _context: dict[str, Any]) -> bool:
        return isinstance(data, QuerySet | Page)

    def serialize(self, data: Any, context: dict[str, Any]) -> Any:
        return [
            context['serializer'].serialize(
                item,
                context.get('user'),
                context.get('permission_checker'),
                context['exclude'],
                context['max_depth'] - 1
            )
            for item in data
        ]


class DictSerializer(TypeSerializer):
    def can_serialize(self, data: Any, _context: dict[str, Any]) -> bool:
        return isinstance(data, dict)

    def serialize(self, data: Any, context: dict[str, Any]) -> Any:
        result = {}
        excluded_keys = context['exclude']

        for k, v in data.items():
            if k in excluded_keys:
                continue

            result[k] = context['serializer'].serialize(
                v,
                context.get('user'),
                context.get('permission_checker'),
                context['exclude'],
                context['max_depth'] - 1
            )

        return result


class QueryDictSerializer(TypeSerializer):
    def can_serialize(self, data: Any, _context: dict[str, Any]) -> bool:
        return isinstance(data, QueryDict)

    def serialize(self, data: Any, context: dict[str, Any]) -> Any:
        result = {}
        excluded_keys = context['exclude']

        for k in data:
            if k in excluded_keys:
                continue

            values = data.getlist(k)

            if len(values) == 1:
                result[k] = context['serializer'].serialize(
                    values[0],
                    context.get('user'),
                    context.get('permission_checker'),
                    context['exclude'],
                    context['max_depth'] - 1
                )
            else:
                result[k] = context['serializer'].serialize(
                    values,
                    context.get('user'),
                    context.get('permission_checker'),
                    context['exclude'],
                    context['max_depth'] - 1
                )

        return result


class ListOrTupleSerializer(TypeSerializer):
    def can_serialize(self, data: Any, _context: dict[str, Any]) -> bool:
        return isinstance(data, list | tuple)

    def serialize(self, data: Any, context: dict[str, Any]) -> Any:
        return [
            context['serializer'].serialize(
                item,
                context.get('user'),
                context.get('permission_checker'),
                context['exclude'],
                context['max_depth'] - 1
            )
            for item in data
        ]


class SetSerializer(TypeSerializer):
    def can_serialize(self, data: Any, _context: dict[str, Any]) -> bool:
        return isinstance(data, set)

    def serialize(self, data: Any, context: dict[str, Any]) -> Any:
        return [
            context['serializer'].serialize(
                item,
                context.get('user'),
                context.get('permission_checker'),
                context['exclude'],
                context['max_depth'] - 1
            )
            for item in data
        ]


class ObjectSerializer(TypeSerializer):
    def can_serialize(self, data: Any, _context: dict[str, Any]) -> bool:
        return hasattr(data, '__dict__')

    def serialize(self, data: Any, context: dict[str, Any]) -> Any:
        obj = {
            k: v for k, v in data.__dict__.items()
            if not k.startswith('_') and not callable(v)
        }

        return context['serializer'].serialize(
            obj,
            context.get('user'),
            context.get('permission_checker'),
            context['exclude'],
            context['max_depth'] - 1
        )


class FallbackSerializer(TypeSerializer):
    def can_serialize(self, _data: Any, _context: dict[str, Any]) -> bool:
        return True

    def serialize(self, data: Any, _context: dict[str, Any]) -> Any:
        return str(data)


class ContextDataSerializer:
    def __init__(self):
        self.serializers = [
            NoneSerializer(),
            PrimitiveSerializer(),
            DateTimeSerializer(),
            DecimalSerializer(),
            UUIDSerializer(),
            EnumSerializer(),
            ChoicesSerializer(),
            ModelSerializer(),
            QuerySetSerializer(),
            DictSerializer(),
            QueryDictSerializer(),
            ListOrTupleSerializer(),
            SetSerializer(),
            ObjectSerializer(),
            FallbackSerializer(),
        ]

    def register_serializer(self, serializer: TypeSerializer, index: int | None = None) -> None:
        if index is None:
            self.serializers.insert(-1, serializer)
        else:
            self.serializers.insert(index, serializer)

    def serialize(
        self,
        data: Any,
        user: User | None = None,
        permission_checker: Callable | None = None,
        exclude: list[str] | set[str] | tuple | None = None,
        max_depth: int = 10
    ) -> Any:
        if max_depth <= 0:
            return str(data)

        context = {
            'serializer': self,
            'user': user,
            'permission_checker': permission_checker,
            'exclude': set(exclude or []),
            'max_depth': max_depth
        }

        for serializer in self.serializers:
            if serializer.can_serialize(data, context):
                return serializer.serialize(data, context)

    @staticmethod
    def _is_choices_list(data: Any) -> bool:
        if not isinstance(data, list | tuple):
            return False

        return all(
            isinstance(item, list | tuple) and
            len(item) == 2 and
            isinstance(item[1], str)
            for item in data
        )

    @staticmethod
    def _is_json(data: str) -> bool:
        if not isinstance(data, str):
            return False

        data = data.strip()

        if not (
            (data.startswith('{') and data.endswith('}')) or
            (data.startswith('[') and data.endswith(']'))
        ):
            return False

        try:
            json.loads(data)
        except (json.JSONDecodeError, ValueError):
            return False
        else:
            return True


context_serializer = ContextDataSerializer()

def serialize_context(
    data: Any,
    exclude: list[str] | set[str] | tuple | None = None,
    max_depth: int = 10,
    user: User | None = None,
    permission_checker: Callable | None = None,
) -> Any:
    return context_serializer.serialize(
        data,
        exclude=exclude,
        max_depth=max_depth,
        user=user,
        permission_checker=permission_checker
    )
