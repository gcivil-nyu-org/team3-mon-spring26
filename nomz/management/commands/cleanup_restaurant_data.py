from django.core.management.base import BaseCommand
from django.db.models import Q

from nomz.models import Restaurant


class Command(BaseCommand):
    help = "Deactivate orphan/non-mappable restaurants to keep search/map data clean."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Apply deactivation. Without this flag, only prints counts.",
        )

    def handle(self, *args, **options):
        orphan_qs = Restaurant.objects.filter(
            is_active=True,
            latitude__isnull=True,
            longitude__isnull=True,
            owner__isnull=True,
            sources__isnull=True,
            reviews__isnull=True,
            photos__isnull=True,
        ).distinct()

        orphan_count = orphan_qs.count()
        geocoded_active = Restaurant.objects.filter(
            is_active=True,
            latitude__isnull=False,
            longitude__isnull=False,
        ).count()
        api_eligible_after = Restaurant.objects.filter(
            Q(owner__userprofile__is_approved=True) | Q(owner__isnull=True),
            is_active=True,
            latitude__isnull=False,
            longitude__isnull=False,
        ).count()

        self.stdout.write(f"Candidates to deactivate: {orphan_count}")
        self.stdout.write(f"Geocoded active restaurants: {geocoded_active}")
        self.stdout.write(f"Current map/API eligible restaurants: {api_eligible_after}")

        if not options["apply"]:
            self.stdout.write(
                self.style.WARNING(
                    "Dry run only. Re-run with --apply to deactivate candidates."
                )
            )
            return

        updated = orphan_qs.update(is_active=False)
        self.stdout.write(self.style.SUCCESS(f"Deactivated {updated} restaurant(s)."))
