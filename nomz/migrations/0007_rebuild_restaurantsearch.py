from django.db import migrations


def rebuild_restaurant_search(apps, schema_editor):
    restaurant_model = apps.get_model("nomz", "Restaurant")
    search_model = apps.get_model("nomz", "RestaurantSearch")

    search_model.objects.all().delete()

    rows = []
    for restaurant in restaurant_model.objects.all().iterator():
        neighborhood = (restaurant.neighborhood or restaurant.borough or "")[:100]
        cuisine = (restaurant.cuisine or restaurant.cuisine_type or "").strip()
        if not cuisine and restaurant.cuisine_tags:
            cuisine = ", ".join(
                str(tag).strip() for tag in restaurant.cuisine_tags if str(tag).strip()
            )
        cuisine = cuisine[:100]

        rows.append(
            search_model(
                name=(restaurant.name or "")[:200],
                neighborhood=neighborhood,
                description=restaurant.description or "",
                cuisine=cuisine,
            )
        )

        if len(rows) >= 1000:
            search_model.objects.bulk_create(rows, batch_size=1000)
            rows = []

    if rows:
        search_model.objects.bulk_create(rows, batch_size=1000)


def reverse_rebuild_restaurant_search(apps, schema_editor):
    search_model = apps.get_model("nomz", "RestaurantSearch")
    search_model.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("nomz", "0006_restaurantsearch"),
    ]

    operations = [
        migrations.RunPython(
            code=rebuild_restaurant_search,
            reverse_code=reverse_rebuild_restaurant_search,
        ),
    ]
