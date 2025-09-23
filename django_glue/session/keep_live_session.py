from time import time
from typing import Iterable

from django_glue.conf import settings
from django_glue.session.session import BaseGlueSession


class KeepLiveSession(BaseGlueSession):
    """
        Used to keep glue session data live for a set amount of time.
        Functionality to handle multiple windows/tabs.
    """
    _session_key: str = settings.DJANGO_GLUE_KEEP_LIVE_SESSION_NAME

    def clean_and_get_expired_unique_names(self) -> list:
        expired_unique_names = []

        for key, val in self.session.items():
            if time() > val:
                expired_unique_names.append(key)

        for expired_unique_name in expired_unique_names:
            self.session.pop(expired_unique_name)

        self.set_modified()

        return expired_unique_names

    @staticmethod
    def get_next_expire_time() -> float:
        return time() + settings.DJANGO_GLUE_KEEP_LIVE_EXPIRE_TIME_SECONDS

    def set_unique_name(self, unique_name: str) -> None:
        self.session.setdefault(unique_name, self.get_next_expire_time())
        self.set_modified()

    def update_unique_names(self, unique_names: Iterable[str]) -> None:
        for unique_name in unique_names:
            if unique_name in self.session:
                self.session[unique_name] = self.get_next_expire_time()

        self.set_modified()
