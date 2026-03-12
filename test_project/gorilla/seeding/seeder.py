from __future__ import annotations

from faker import Faker

from test_project.gorilla.models import Gorilla, Skill


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


SKILL_NAMES = [
    ('Chest Pound', 'Intimidating display of dominance'),
    ('Ground Slam', 'Devastating ground attack'),
    ('Tree Swing', 'Acrobatic aerial maneuver'),
    ('Vine Whip', 'Long-range vine attack'),
    ('Jungle Roar', 'Terrifying battle cry'),
    ('Banana Throw', 'Surprising ranged attack'),
    ('Silverback Charge', 'Powerful rushing tackle'),
    ('Knuckle Walk', 'Defensive stance technique'),
    ('Primal Rage', 'Berserker fury mode'),
    ('Forest Camouflage', 'Stealth and ambush tactics'),
]


class SkillSeeder:
    """Seeder for Skill model."""

    def __init__(self):
        self.fake = Faker()

    def create_skill(self, name: str, description: str) -> Skill:
        """Create a single Skill."""
        return Skill.objects.create(
            name=name,
            description=description,
            difficulty=self.fake.random_int(min=1, max=10),
            level=self.fake.random_int(min=1, max=100),
        )

    @classmethod
    def seed_database(cls) -> list[Skill]:
        """Seed the database with predefined skills."""
        seeder = cls()
        skills = []
        for name, description in SKILL_NAMES:
            skill, created = Skill.objects.get_or_create(
                name=name,
                defaults={
                    'description': description,
                    'difficulty': seeder.fake.random_int(min=1, max=10),
                    'level': seeder.fake.random_int(min=1, max=100),
                }
            )
            skills.append(skill)
        return skills


class GorillaSeeder:
    """Simple seeder for Gorilla model using Faker."""

    def __init__(self):
        self.fake = Faker()

    def create_gorilla(self, skills: list[Skill] | None = None) -> Gorilla:
        """Create a single Gorilla with fake data."""
        name = self.fake.random_element(GORILLA_NAMES)
        suffix = self.fake.random_int(min=1, max=99)

        gorilla = Gorilla.objects.create(
            name=f"{name} #{suffix}",
            description=self.fake.paragraph(nb_sentences=2),
            age=self.fake.random_int(min=10, max=45),
            weight=round(self.fake.pyfloat(min_value=150, max_value=400), 1),
            height=round(self.fake.pyfloat(min_value=1.2, max_value=2.2), 2),
            rank_points=self.fake.random_int(min=0, max=5000),
        )

        # Assign random skills if available
        if skills:
            random_skills = self.fake.random_elements(
                skills,
                length=self.fake.random_int(min=1, max=min(4, len(skills))),
                unique=True
            )
            gorilla.skills.set(random_skills)

        return gorilla

    @classmethod
    def seed_database(cls, count: int = 10) -> list[Gorilla]:
        """Seed the database with the specified number of Gorillas."""
        # Ensure skills exist first
        skills = SkillSeeder.seed_database()

        seeder = cls()
        return [seeder.create_gorilla(skills=skills) for _ in range(count)]
