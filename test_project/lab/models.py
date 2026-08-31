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


class Specimen(models.Model):
    name = models.CharField(max_length=64)
    species = models.CharField(max_length=32, choices=[(species, species) for species in SPECIES])
    weight = models.FloatField(help_text='Weight in milligrams')
    catalogue_number = models.PositiveIntegerField(unique=True)

    class Meta:
        db_table = 'lab_specimen'
        ordering = ['catalogue_number']

    def __str__(self) -> str:
        return f'{self.name} ({self.catalogue_number})'

    @classmethod
    def seed(cls, count: int, batch_size: int = 5000) -> int:
        start = (cls.objects.aggregate(last=models.Max('catalogue_number'))['last'] or 0) + 1

        specimens = (
            cls(
                name=f'{ADJECTIVES[index % len(ADJECTIVES)]} {NOUNS[(index // len(ADJECTIVES)) % len(NOUNS)]}',
                species=SPECIES[index % len(SPECIES)],
                weight=round(1 + (index * 7919) % 400 + (index % 10) / 10, 1),
                catalogue_number=index,
            )
            for index in range(start, start + count)
        )

        with transaction.atomic():
            created = cls.objects.bulk_create(specimens, batch_size=batch_size)

        return len(created)
