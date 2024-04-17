from abc import ABC


class Session(ABC):
    def __init__(self, request):
        self.request = request
