from __future__ import annotations

from faker import Faker

from test_project.fight.models import Fight
from test_project.fight.choices import (
    LocationChoices,
    WeatherConditionChoices,
    TerrainTypeChoices,
    FightStatusChoices,
)
from test_project.gorilla.models import Gorilla


FIGHT_NAME_TEMPLATES = [
    "Battle of the {location}",
    "Clash in the {location}",
    "{location} Showdown",
    "Rumble at {location}",
    "The {location} Brawl",
    "Championship at {location}",
    "Legends of {location}",
    "Thunder in {location}",
]

LOCATION_NAMES = {
    'thu': 'Thunderdome',
    'col': 'Colosseum',
    'aml': 'Abandoned Mall',
    'nin': 'Ninja Dojo',
    'din': 'Dinosaur Island',
    'vol': 'Volcano Crater',
    'pir': 'Pirate Cove',
    'ali': 'Alien Wasteland',
}


class FightSeeder:
    """Simple seeder for Fight model using Faker."""

    def __init__(self):
        self.fake = Faker()
        self.locations = [choice[0] for choice in LocationChoices.choices]
        self.weather = [choice[0] for choice in WeatherConditionChoices.choices]
        self.terrain = [choice[0] for choice in TerrainTypeChoices.choices]
        self.statuses = [choice[0] for choice in FightStatusChoices.choices]

    def create_fight(self, gorillas: list[Gorilla]) -> Fight:
        """Create a single Fight with fake data."""
        if len(gorillas) < 2:
            raise ValueError("Need at least 2 gorillas to create a fight")

        red_corner = self.fake.random_element(gorillas)
        blue_corner = self.fake.random_element([g for g in gorillas if g != red_corner])

        location = self.fake.random_element(self.locations)
        location_name = LOCATION_NAMES.get(location, 'Arena')
        name_template = self.fake.random_element(FIGHT_NAME_TEMPLATES)
        name = name_template.format(location=location_name)

        status = self.fake.random_element(self.statuses)

        fight = Fight.objects.create(
            name=name,
            description=self.fake.paragraph(nb_sentences=2),
            red_corner=red_corner,
            blue_corner=blue_corner,
            location=location,
            weather_conditions=self.fake.random_element(self.weather),
            terrain_type=self.fake.random_element(self.terrain),
            status=status,
            spectator_count=self.fake.random_int(min=100, max=50000),
        )

        # If completed, set winner and loser
        if status == 'cmp':
            winner = self.fake.random_element([red_corner, blue_corner])
            loser = blue_corner if winner == red_corner else red_corner
            fight.winner = winner
            fight.loser = loser
            fight.save()

        return fight

    @classmethod
    def seed_database(cls, count: int = 5) -> list[Fight]:
        """Seed the database with the specified number of Fights."""
        gorillas = list(Gorilla.objects.all())
        if len(gorillas) < 2:
            raise ValueError("Need at least 2 gorillas in database to seed fights")

        seeder = cls()
        return [seeder.create_fight(gorillas) for _ in range(count)]
