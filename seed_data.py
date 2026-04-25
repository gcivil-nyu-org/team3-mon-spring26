import os
import django

# 1. Setup Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "restaurants.settings")
django.setup()

# Django imports must come after django.setup()
from django.contrib.auth.models import User  # noqa: E402
from nomz.models import RestaurantSearch, Restaurant, UserProfile  # noqa: E402


def seed_restaurants():
    # 1. Clear existing data
    print("Cleaning up old restaurant data...")
    RestaurantSearch.objects.all().delete()
    Restaurant.objects.all().delete()

    # 2. Ensure we have a Restaurant Owner user
    owner_user, created = User.objects.get_or_create(username="rest1")
    if created:
        owner_user.set_password("password123")
        owner_user.save()

    UserProfile.objects.get_or_create(user=owner_user, role="restaurant")

    # 3. Create a real Restaurant Profile for the dashboard to count
    Restaurant.objects.create(
        owner=owner_user,
        name="The Daily Grind (Official)",
        neighborhood="Downtown",
        cuisine="Coffee & Bakery",
        description="Our official profile for artisan coffee.",
        address="123 Coffee Lane, NYC",
        is_active=True,
    )

    # 4. Sample data for RestaurantSearch (Legacy/Search compatibility) and Restaurant models
    restaurants = [
        {
            "name": "The Daily Grind",
            "neighborhood": "Downtown",
            "cuisine": "Coffee & Bakery",
            "cuisine_type": "other",
            "price_range": "$$",
            "description": "Artisan coffee and fresh pastries in a cozy, industrial atmosphere.",
            "address": "123 Coffee Lane, NYC",
        },
        {
            "name": "Campus Pizza",
            "neighborhood": "North Campus",
            "cuisine": "Italian",
            "cuisine_type": "italian",
            "price_range": "$",
            "description": "Authentic wood-fired pizzas with a student-friendly price tag.",
            "address": "456 University Ave, NYC",
        },
        {
            "name": "Sushi Zen",
            "neighborhood": "Downtown",
            "cuisine": "Japanese",
            "cuisine_type": "japanese",
            "price_range": "$$$",
            "description": "Fresh sashimi and innovative rolls served in a minimalist setting.",
            "address": "789 Sushi St, NYC",
        },
        {
            "name": "Burger Haven",
            "neighborhood": "West End",
            "cuisine": "American",
            "cuisine_type": "american",
            "price_range": "$$",
            "description": "Gourmet burgers with locally sourced beef and hand-cut fries.",
            "address": "101 Burger Blvd, NYC",
        },
        {
            "name": "Taco Fiesta",
            "neighborhood": "North Campus",
            "cuisine": "Mexican",
            "cuisine_type": "mexican",
            "price_range": "$",
            "description": "Vibrant street tacos and the best margaritas in the city.",
            "address": "202 Taco Way, NYC",
        },
        {
            "name": "The Green Leaf",
            "neighborhood": "East Side",
            "cuisine": "Vegan",
            "cuisine_type": "vegan",
            "price_range": "$$",
            "description": "Plant-based comfort food that even meat-eaters will love.",
            "address": "303 Vegan Rd, NYC",
        },
    ]

    print(f"Seeding {len(restaurants)} restaurants...")
    for r in restaurants:
        # Create Restaurant object
        Restaurant.objects.create(
            name=r["name"],
            neighborhood=r["neighborhood"],
            cuisine=r["cuisine"],
            cuisine_type=r["cuisine_type"],
            price_range=r["price_range"],
            description=r["description"],
            address=r["address"],
            is_active=True,
        )
        # Also create RestaurantSearch for compatibility
        RestaurantSearch.objects.create(
            name=r["name"],
            neighborhood=r["neighborhood"],
            cuisine=r["cuisine"],
            description=r["description"],
        )

    print("Done! Your local database is ready for testing.")


def main():
    seed_restaurants()


if __name__ == "__main__":
    main()
