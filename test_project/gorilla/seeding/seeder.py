from __future__ import annotations

from faker import Faker

from test_project.gorilla.models import Gorilla
from test_project.gorilla.choices import FightStyleChoices


GORILLA_NAMES = [
    'Kong the Destroyer',
    'Silverback Sam',
    'Mighty Max',
    'Thunder Fist',
    'Iron Jaw Joe',
    'Banana Basher',
    'Jungle Justice',
    'Primal Pete',
    'Gorilla Grit',
    'Rampage Rex',
    'Knuckle Crusher',
    'Wild Warden',
    'Brutus the Beast',
    'Fury Fang',
    'Savage Steve',
]


class GorillaSeeder:
    """Simple seeder for Gorilla model using Faker."""

    def __init__(self):
        self.fake = Faker()
        self.fight_styles = [choice[0] for choice in FightStyleChoices.choices]

    def create_gorilla(self) -> Gorilla:
        """Create a single Gorilla with fake data."""
        name = self.fake.random_element(GORILLA_NAMES)
        suffix = self.fake.random_int(min=1, max=99)

        return Gorilla.objects.create(
            name=f"{name} #{suffix}",
            description=self.fake.paragraph(nb_sentences=2),
            age=self.fake.random_int(min=10, max=45),
            weight=round(self.fake.pyfloat(min_value=150, max_value=400), 1),
            height=round(self.fake.pyfloat(min_value=1.2, max_value=2.2), 2),
            fight_style=self.fake.random_element(self.fight_styles),
            rank_points=self.fake.random_int(min=0, max=5000),
        )

    @classmethod
    def seed_database(cls, count: int = 10) -> list[Gorilla]:
        """Seed the database with the specified number of Gorillas."""
        seeder = cls()
        return [seeder.create_gorilla() for _ in range(count)]
