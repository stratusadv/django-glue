from django_glue.access.access import GlueAccess


class GorillaService:
    def __init__(self, gorilla):
        self.gorilla = gorilla

    def increment_age_and_save(self):
        self.gorilla.age += 1
        self.gorilla.save()

    class GlueMeta:
        attributes = [
            ('increment_age_and_save', {'access': GlueAccess.CHANGE}),
        ]


class GorillaServiceDescriptor:
    def __get__(self, instance, owner):
        if instance is None:
            return self
        return GorillaService(instance)
