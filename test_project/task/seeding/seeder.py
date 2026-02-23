from __future__ import annotations

from faker import Faker

from test_project.task.models import Task


class TaskSeeder:
    """Simple seeder for Task model using Faker."""

    def __init__(self):
        self.fake = Faker()

    def create_task(self) -> Task:
        """Create a single Task with fake data."""
        return Task.objects.create(
            title=self.fake.sentence(nb_words=4)[:50],
            description=self.fake.paragraph(nb_sentences=2),
            done=self.fake.boolean(),
            order=self.fake.random_int(min=1, max=1000),
        )

    @classmethod
    def seed_database(cls, count: int = 10) -> list[Task]:
        """Seed the database with the specified number of Tasks."""
        seeder = cls()
        return [seeder.create_task() for _ in range(count)]