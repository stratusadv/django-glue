import os
import sys
from pathlib import Path

# Add project root to path so test_project is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_project.base_settings')

application = get_wsgi_application()

print('Seeding Gorilla\'s...')
from test_project.gorilla.seeding.seed import *

print('Seeding Fight\'s...')
from test_project.fight.seeding.seed import *

print('Done!')