import django
django.setup()

print('seeding gorillas')
from test_project.app.gorilla.seeding.seed import *

# print('seeding capabilities')
# from test_project.app.capability.seeding.seed import *
# from test_project.app.gorilla.capability.seeding.seed import *
#
# print('seeding fights')
# from test_project.app.fight.seeding.seed import *
# from test_project.app.fight.round.seeding.seed import *
#
