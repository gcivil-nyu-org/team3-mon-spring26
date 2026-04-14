import os

import django


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "restaurants.settings")
django.setup()
