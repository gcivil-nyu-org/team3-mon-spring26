import os
import django

# 1. Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'restaurants.settings')
django.setup()

from nomz.models import RestaurantSearch

def seed_restaurants():
    # Clear existing data to avoid duplicates during testing
    print("Cleaning up old restaurant data...")
    RestaurantSearch.objects.all().delete()

    # Sample data based on common neighborhood names
    restaurants = [
        {
            "name": "The Daily Grind",
            "neighborhood": "Downtown",
            "cuisine": "Coffee & Bakery",
            "description": "Artisan coffee and fresh pastries in a cozy, industrial atmosphere."
        },
        {
            "name": "Campus Pizza",
            "neighborhood": "North Campus",
            "cuisine": "Italian",
            "description": "Authentic wood-fired pizzas with a student-friendly price tag."
        },
        {
            "name": "Sushi Zen",
            "neighborhood": "Downtown",
            "cuisine": "Japanese",
            "description": "Fresh sashimi and innovative rolls served in a minimalist setting."
        },
        {
            "name": "Burger Haven",
            "neighborhood": "West End",
            "cuisine": "American",
            "description": "Gourmet burgers with locally sourced beef and hand-cut fries."
        },
        {
            "name": "Taco Fiesta",
            "neighborhood": "North Campus",
            "cuisine": "Mexican",
            "description": "Vibrant street tacos and the best margaritas in the city."
        },
        {
            "name": "The Green Leaf",
            "neighborhood": "East Side",
            "cuisine": "Vegan",
            "description": "Plant-based comfort food that even meat-eaters will love."
        }
    ]

    print(f"Seeding {len(restaurants)} restaurants...")
    for r in restaurants:
        RestaurantSearch.objects.create(**r)
    
    print("Done! Your local database is ready for testing.")

if __name__ == "__main__":
    seed_restaurants()