from time import time


class GlueKey:
    _instance = None

    def __new__(cls, *args, **kwargs):
        import uuid

        if cls._instance is None:
            cls._instance = object.__new__(cls)
            cls.value = str(uuid.uuid4())
            cls.set_expire_time(cls._instance)
        elif time() > cls._instance.expire_time:
            cls._instance.value = str(uuid.uuid4())
            cls.set_expire_time(cls._instance)
        else:
            cls.set_expire_time(cls._instance)

        return cls._instance

    def set_expire_time(self):
        self.expire_time = time() + 60.0
