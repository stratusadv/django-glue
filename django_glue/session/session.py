from abc import ABC


class Session(ABC):
    # Todo: This can be remove if there isn't any over lapping functionality.
    def __init__(self, request):
        self.request = request
