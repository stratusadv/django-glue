from time import time

from django_glue.conf import settings


class KeepLiveSession:
    """
        Used to keep glue session data live for a set amount of time.
        Functionality to handle multiple windows/tabs.
    """
    def __init__(self, request):
        self.request = request
        self.session = request.session.setdefault(settings.DJANGO_GLUE_KEEP_LIVE_SESSION_NAME, dict())

    def __getitem__(self, key):
        return self.session[key]

    def __setitem__(self, key, value):
        self.session[key] = value

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
    def get_next_expire_time():
        return time() + settings.DJANGO_GLUE_KEEP_LIVE_EXPIRE_TIME_SECONDS

    def set_unique_name(self, unique_name):
        self.session.setdefault(unique_name, self.get_next_expire_time())

        self.set_modified()

    def set_modified(self):
        self.request.session.modified = True

    def update_unique_names(self, unique_names: list):
        for unique_name in unique_names:
            if unique_name in self.session:
                self.session[unique_name] = self.get_next_expire_time()

        self.set_modified()
