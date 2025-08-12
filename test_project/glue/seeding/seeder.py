from django_spire.contrib.seeding import DjangoModelSeeder
from test_project.app.capability.models import Capability


class CapabilitySeeder(DjangoModelSeeder):
    model_class = Capability
    cache_name = 'capability_seeder'
    cache_seed = True
    default_to = 'faker'
    fields = {
        'id': 'exclude',
        'name': ('llm', 'Generate a name for an MMA fighting gorilla capability'),
        'description': ('llm', 'Describe this MMA fighting gorilla capability in detail'),
    }