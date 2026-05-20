from abc import ABC, abstractmethod

from django.http import JsonResponse, HttpRequest, HttpResponse


class BaseResolver(ABC):
    @abstractmethod
    def __init__(self, request: HttpRequest, **kwargs) -> None:
        pass

    @abstractmethod
    def resolve(self) -> JsonResponse | HttpResponse:
        pass
