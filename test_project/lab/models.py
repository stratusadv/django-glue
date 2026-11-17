from django.db import models, transaction

ADJECTIVES = (
    'Amber', 'Brass', 'Cobalt', 'Dusky', 'Ember', 'Frost', 'Gilded', 'Hollow',
    'Ivory', 'Jade', 'Kindled', 'Lunar', 'Mossy', 'Nimble', 'Obsidian', 'Pale',
    'Quiet', 'Rusty', 'Silver', 'Timber', 'Umber', 'Velvet', 'Wild', 'Zinc',
)

NOUNS = (
    'Beetle', 'Cricket', 'Dragonfly', 'Firefly', 'Hornet', 'Katydid', 'Lacewing',
    'Mantis', 'Moth', 'Scarab', 'Silverfish', 'Weevil',
)

SPECIES = (
    'Coleoptera', 'Diptera', 'Hemiptera', 'Hymenoptera', 'Lepidoptera', 'Odonata', 'Orthoptera',
)

COLLECTORS = (
    'Agassiz', 'Audubon', 'Bates', 'Cuvier', 'Darwin', 'Fabre', 'Haeckel', 'Humboldt',
    'Lamarck', 'Linnaeus', 'Merian', 'Wallace',
)

HABITATS = (
    'Canopy', 'Cave', 'Desert', 'Forest', 'Meadow', 'Riverbank', 'Tundra', 'Wetland',
)


class Collector(models.Model):
    name = models.CharField(max_length=64, unique=True)

    class Meta:
        db_table = 'lab_collector'
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class Habitat(models.Model):
    name = models.CharField(max_length=32, unique=True)

    class Meta:
        db_table = 'lab_habitat'
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class Specimen(models.Model):
    name = models.CharField(max_length=64)
    species = models.CharField(max_length=32, choices=[(species, species) for species in SPECIES])
    weight = models.FloatField(help_text='Weight in milligrams')
    catalogue_number = models.PositiveIntegerField(unique=True)
    collector = models.ForeignKey(
        Collector,
        null=True,
        on_delete=models.SET_NULL,
        related_name='specimens',
    )
    habitats = models.ManyToManyField(Habitat, blank=True, related_name='specimens')

    class Meta:
        db_table = 'lab_specimen'
        ordering = ['catalogue_number']

    def __str__(self) -> str:
        return f'{self.name} ({self.catalogue_number})'

    @classmethod
    def seed(cls, count: int, batch_size: int = 5000) -> int:
        start = (cls.objects.aggregate(last=models.Max('catalogue_number'))['last'] or 0) + 1

        with transaction.atomic():
            Collector.objects.bulk_create(
                [Collector(name=name) for name in COLLECTORS],
                ignore_conflicts=True,
            )
            Habitat.objects.bulk_create(
                [Habitat(name=name) for name in HABITATS],
                ignore_conflicts=True,
            )
            collectors = list(Collector.objects.filter(name__in=COLLECTORS))
            habitats = list(Habitat.objects.filter(name__in=HABITATS))

            specimens = (
                cls(
                    name=f'{ADJECTIVES[index % len(ADJECTIVES)]} {NOUNS[(index // len(ADJECTIVES)) % len(NOUNS)]}',
                    species=SPECIES[index % len(SPECIES)],
                    weight=round(1 + (index * 7919) % 400 + (index % 10) / 10, 1),
                    catalogue_number=index,
                    collector=collectors[index % len(collectors)],
                )
                for index in range(start, start + count)
            )
            created = cls.objects.bulk_create(specimens, batch_size=batch_size)

            # Two habitats each, so every row has a to-many value to read.
            cls.habitats.through.objects.bulk_create(
                (
                    cls.habitats.through(specimen_id=specimen.pk, habitat_id=habitat.pk)
                    for specimen in created
                    for habitat in (
                        habitats[specimen.catalogue_number % len(habitats)],
                        habitats[(specimen.catalogue_number + 3) % len(habitats)],
                    )
                ),
                batch_size=batch_size,
            )

        return len(created)
