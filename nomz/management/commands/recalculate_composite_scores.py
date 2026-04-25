from django.core.management.base import BaseCommand
from nomz.models import Restaurant
from nomz.scoring import refresh_restaurant_composite


class Command(BaseCommand):
    help = "Recalculate and persist composite scores for restaurants."

    def add_arguments(self, parser):
        parser.add_argument(
            "--only-missing",
            action="store_true",
            help="Recalculate only restaurants with missing composite_score.",
        )
        parser.add_argument(
            "--include-inactive",
            action="store_true",
            help="Include inactive restaurants in recalculation.",
        )
        parser.add_argument(
            "--restaurant-id",
            type=int,
            action="append",
            dest="restaurant_ids",
            help="Recalculate only a specific restaurant ID. Can be provided multiple times.",
        )

    def handle(self, *args, **options):
        queryset = Restaurant.objects.all().order_by("id")
        restaurant_ids = options.get("restaurant_ids") or []
        if isinstance(restaurant_ids, int):
            restaurant_ids = [restaurant_ids]
        if restaurant_ids:
            queryset = queryset.filter(id__in=restaurant_ids)
        if not options["include_inactive"]:
            queryset = queryset.filter(is_active=True)
        if options["only_missing"]:
            queryset = queryset.filter(composite_score__isnull=True)

        total = queryset.count()
        updated = 0
        anomaly_flags = 0
        for restaurant in queryset.iterator():
            score_data = refresh_restaurant_composite(
                restaurant,
                trigger_source="management_command",
                trigger_note="recalculate_composite_scores",
            )
            updated += 1
            anomaly_flags += int(score_data.get("anomaly_count") or 0)

        self.stdout.write(
            self.style.SUCCESS(
                (
                    f"Recalculated composite scores for {updated}/{total} restaurant(s). "
                    f"Anomaly flags detected: {anomaly_flags}."
                )
            )
        )
