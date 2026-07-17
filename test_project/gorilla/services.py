from django_glue.shortcuts.glue import Glue


class GorillaService:
    def __init__(self, gorilla):
        self.gorilla = gorilla

    @Glue.attribute(access=Glue.Access.CHANGE)
    def increment_age(self):
        self.gorilla.age += 1
        self.gorilla.save()

    def increment_age_and_save(self):
        self.increment_age()


class GorillaServiceDescriptor:
    def __get__(self, instance, owner):
        if instance is None:
            return self
        return GorillaService(instance)
