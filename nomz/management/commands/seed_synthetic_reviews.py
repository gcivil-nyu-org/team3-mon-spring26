from __future__ import annotations

import random

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from nomz.models import Restaurant, Review
from nomz.scoring import refresh_restaurant_composite

REVIEW_TEXT_SNIPPETS = [
    "Solid neighborhood spot with consistent food.",
    "Service was smooth and friendly.",
    "Good value overall for the price point.",
    "Ambience was pleasant and clean.",
    "Would return again for a casual meal.",
    "Great option when looking for quick dinner plans.",
    "Portions were fair and staff was helpful.",
    "Convenient location with decent seating.",
]


def _bounded_round(value: float) -> int:
    return max(1, min(5, int(round(value))))


class Command(BaseCommand):
    help = "Seed synthetic multi-parameter reviews for restaurants without inspection data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Apply writes. Without this flag, command runs in dry mode.",
        )
        parser.add_argument(
            "--include-inactive",
            action="store_true",
            help="Include inactive restaurants as review-seeding candidates.",
        )
        parser.add_argument(
            "--min-reviews",
            type=int,
            default=3,
            help="Minimum synthetic reviews per restaurant.",
        )
        parser.add_argument(
            "--max-reviews",
            type=int,
            default=6,
            help="Maximum synthetic reviews per restaurant.",
        )
        parser.add_argument(
            "--reviewer-pool-size",
            type=int,
            default=60,
            help="How many synthetic reviewer accounts to use.",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=20260328,
            help="Random seed to make results reproducible.",
        )

    def handle(self, *args, **options):
        rng = random.Random(options["seed"])
        min_reviews = max(1, int(options["min_reviews"]))
        max_reviews = max(min_reviews, int(options["max_reviews"]))
        reviewer_pool_size = max(5, int(options["reviewer_pool_size"]))
        should_apply = options["apply"]

        restaurant_qs = Restaurant.objects.filter(inspections__isnull=True).distinct()
        if not options["include_inactive"]:
            restaurant_qs = restaurant_qs.filter(is_active=True)
        restaurant_qs = restaurant_qs.filter(reviews__isnull=True).distinct()

        restaurant_ids = list(restaurant_qs.values_list("id", flat=True))
        total_targets = len(restaurant_ids)

        self.stdout.write(
            f"Candidate restaurants without inspections/reviews: {total_targets}"
        )
        if not should_apply:
            self.stdout.write(
                self.style.WARNING(
                    "Dry run only. Re-run with --apply to create synthetic reviews."
                )
            )
            return

        reviewers = []
        for idx in range(1, reviewer_pool_size + 1):
            username = f"synthetic_reviewer_{idx:03d}"
            reviewer, _ = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": f"{username}@nomz.local",
                    "is_active": True,
                },
            )
            reviewers.append(reviewer)

        created_reviews = 0
        touched_restaurant_ids = []
        review_batch = []

        restaurant_lookup = {
            item.id: item
            for item in Restaurant.objects.filter(id__in=restaurant_ids).only(
                "id",
                "name",
                "borough",
                "cuisine_type",
                "price_range",
            )
        }

        for restaurant_id in restaurant_ids:
            restaurant = restaurant_lookup[restaurant_id]
            touched_restaurant_ids.append(restaurant_id)
            local_rng = random.Random((options["seed"] * 37) + restaurant_id)

            borough_bias = {
                "manhattan": 4.1,
                "brooklyn": 3.9,
                "queens": 3.8,
                "bronx": 3.7,
                "staten island": 3.8,
            }.get((restaurant.borough or "").strip().lower(), 3.8)
            price_bias = {
                "$": 3.7,
                "$$": 3.9,
                "$$$": 4.0,
                "$$$$": 4.1,
            }.get((restaurant.price_range or "$$").strip(), 3.9)

            review_count = local_rng.randint(min_reviews, max_reviews)
            for _ in range(review_count):
                reviewer = rng.choice(reviewers)
                food = _bounded_round(
                    local_rng.gauss((borough_bias + price_bias) / 2, 0.8)
                )
                service = _bounded_round(local_rng.gauss(3.8, 0.9))
                ambience = _bounded_round(local_rng.gauss(price_bias, 0.8))
                location = _bounded_round(local_rng.gauss(borough_bias, 0.7))
                value = _bounded_round(
                    local_rng.gauss(
                        3.9 if restaurant.price_range in {"$", "$$"} else 3.5, 0.8
                    )
                )
                dietary = _bounded_round(local_rng.gauss(3.6, 0.9))
                cleanliness = _bounded_round(local_rng.gauss(4.0, 0.7))
                overall = _bounded_round(
                    (
                        (food * 0.35)
                        + (service * 0.20)
                        + (ambience * 0.15)
                        + (location * 0.10)
                        + (value * 0.10)
                        + (dietary * 0.05)
                        + (cleanliness * 0.05)
                    )
                )

                review_batch.append(
                    Review(
                        restaurant_id=restaurant.id,
                        user_id=reviewer.id,
                        rating=overall,
                        food_quality_rating=food,
                        service_quality_rating=service,
                        ambience_rating=ambience,
                        location_rating=location,
                        value_rating=value,
                        dietary_accommodation_rating=dietary,
                        cleanliness_rating=cleanliness,
                        comment=rng.choice(REVIEW_TEXT_SNIPPETS),
                    )
                )
                created_reviews += 1

        if review_batch:
            Review.objects.bulk_create(review_batch, batch_size=1000)

        refreshed = 0
        for restaurant in Restaurant.objects.filter(id__in=touched_restaurant_ids).only(
            "id"
        ):
            refresh_restaurant_composite(
                restaurant,
                trigger_source="management_command",
                trigger_note="seed_synthetic_reviews",
            )
            refreshed += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Synthetic reviews seeded successfully: "
                f"{created_reviews} reviews across {refreshed} restaurant(s)."
            )
        )
