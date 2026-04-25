from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.utils import timezone
from django.db import models, transaction


class UserProfile(models.Model):
    id = models.AutoField(
        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
    )

    ROLE_CHOICES = [
        ("diner", "Diner"),
        ("restaurant", "Restaurant"),
    ]

    # Links this profile to the built-in Django User
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="diner")
    is_approved = models.BooleanField(
        default=False,
        help_text="Designates whether this business account has been approved by an administrator.",
    )
    is_rejected = models.BooleanField(
        default=False,
        help_text="Designates whether this business account has been rejected by an administrator.",
    )
    is_flagged = models.BooleanField(
        default=False,
        help_text="Publicly flagged for fraudulent activity",
    )

    def __str__(self):
        return f"{self.user.username} - {self.role}"


class RestaurantSearch(models.Model):
    name = models.CharField(max_length=200)
    neighborhood = models.CharField(max_length=100)
    description = models.TextField()
    cuisine = models.CharField(max_length=100)
    # We use a simple CharField for neighborhood to keep it easy for now

    def __str__(self):
        return self.name


class Restaurant(models.Model):
    """
    Restaurant profile model for restaurant owners to manage their business information.
    """

    CUISINE_CHOICES = [
        ("american", "American"),
        ("asian", "Asian"),
        ("italian", "Italian"),
        ("mexican", "Mexican"),
        ("indian", "Indian"),
        ("french", "French"),
        ("japanese", "Japanese"),
        ("chinese", "Chinese"),
        ("thai", "Thai"),
        ("mediterranean", "Mediterranean"),
        ("fusion", "Fusion"),
        ("vegetarian", "Vegetarian"),
        ("vegan", "Vegan"),
        ("other", "Other"),
    ]

    PRICE_CHOICES = [
        ("$", "Budget-Friendly ($)"),
        ("$$", "Moderate ($$)"),
        ("$$$", "Upscale ($$$)"),
        ("$$$$", "Fine Dining ($$$$)"),
    ]

    LOCATION_TYPE_CHOICES = [
        ("indoor", "Indoor"),
        ("outdoor", "Outdoor"),
        ("sidewalk", "Sidewalk"),
        ("mixed", "Mixed"),
        ("unknown", "Unknown"),
    ]

    # Owner and basic owner-editable info
    owner = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="restaurant_profile",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Describe your restaurant, cuisine style, and ambiance",
    )
    address = models.CharField(max_length=500, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    email = models.EmailField(max_length=254, blank=True, null=True)
    cuisine_type = models.CharField(
        max_length=50, choices=CUISINE_CHOICES, default="other"
    )
    price_range = models.CharField(max_length=10, choices=PRICE_CHOICES, default="$$")

    # Operating hours
    days_of_week = [
        ("MON", "Monday"),
        ("TUE", "Tuesday"),
        ("WED", "Wednesday"),
        ("THU", "Thursday"),
        ("FRI", "Friday"),
        ("SAT", "Saturday"),
        ("SUN", "Sunday"),
    ]

    # Hours stored as JSONField for flexibility (optional: can use TimeField pairs)
    hours_open = models.TimeField(
        default="09:00", null=True, blank=True, help_text="Opening time"
    )
    hours_close = models.TimeField(
        default="21:00", null=True, blank=True, help_text="Closing time"
    )

    # Status and availability
    is_active = models.BooleanField(
        default=True, db_index=True, help_text="Profile is visible to users"
    )
    is_flagged = models.BooleanField(
        default=False, help_text="Publicly flagged for fraudulent activity"
    )
    is_temporarily_unavailable = models.BooleanField(
        default=False, help_text="Temporarily mark as unavailable"
    )
    unavailable_reason = models.CharField(max_length=500, blank=True, null=True)
    unavailable_until = models.DateTimeField(blank=True, null=True)

    # Communication settings (Issue #62)
    messaging_enabled = models.BooleanField(
        default=True,
        help_text="Allow diners to send messages to this restaurant",
    )
    response_hours_start = models.TimeField(
        blank=True,
        null=True,
        help_text="Earliest time the restaurant responds to messages",
    )
    response_hours_end = models.TimeField(
        blank=True,
        null=True,
        help_text="Latest time the restaurant responds to messages",
    )

    # Legacy compatibility fields expected by existing views/admin/forms
    neighborhood = models.CharField(max_length=100, blank=True, default="")
    cuisine = models.CharField(max_length=100, blank=True, default="")

    # Ingestion-friendly normalized profile fields
    display_name = models.CharField(max_length=255, blank=True, default="")
    name_normalized = models.CharField(
        max_length=255, db_index=True, blank=True, default=""
    )
    building = models.CharField(max_length=64, blank=True, null=True)
    street = models.CharField(max_length=255, blank=True, null=True)
    borough = models.CharField(max_length=80, blank=True, null=True)
    zip_code = models.CharField(max_length=10, db_index=True, blank=True, null=True)
    cuisine_tags = models.JSONField(default=list, blank=True)

    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=10, decimal_places=6, null=True, blank=True
    )

    composite_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    grade_latest = models.CharField(max_length=16, blank=True, null=True)
    grade_score_latest = models.IntegerField(blank=True, null=True)
    last_inspection_date = models.DateField(blank=True, null=True)
    composite_score_calculated_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["name_normalized", "zip_code"]),
            models.Index(fields=["borough", "zip_code"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["latitude", "longitude"]),
        ]
        ordering = ["name"]

    def __str__(self):
        return self.name

    def is_open_now(self):
        """Check if restaurant is currently open"""
        if not self.is_active or self.is_temporarily_unavailable:
            return False
        if not self.hours_open or not self.hours_close:
            return False
        current_time = timezone.now().time()
        return self.hours_open <= current_time <= self.hours_close

    def can_be_managed_by(self, user):
        """Check if a user can manage this restaurant"""
        return self.owner == user


class RestaurantOwnershipClaim(models.Model):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending Review"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    claimant = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="restaurant_claims",
    )
    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name="ownership_claims",
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    business_email = models.EmailField(blank=True, null=True)
    contact_phone = models.CharField(max_length=32, blank=True, null=True)
    proof_details = models.TextField(
        blank=True,
        help_text="Share links or details proving you manage this restaurant.",
    )
    review_notes = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_restaurant_claims",
    )
    reviewed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["claimant", "status"]),
            models.Index(fields=["restaurant", "status"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.claimant.username} -> {self.restaurant.name} ({self.status})"

    def clean(self):
        if (
            self.restaurant_id
            and self.restaurant.owner_id
            and self.restaurant.owner_id != self.claimant_id
        ):
            raise ValidationError(
                "This restaurant is already claimed by another owner."
            )

        if not self.claimant_id:
            return

        if self.status == self.STATUS_PENDING:
            pending_claim = (
                RestaurantOwnershipClaim.objects.filter(
                    claimant=self.claimant,
                    status=self.STATUS_PENDING,
                )
                .exclude(pk=self.pk)
                .first()
            )
            if pending_claim:
                raise ValidationError("You already have a pending ownership claim.")

            existing_for_restaurant = (
                RestaurantOwnershipClaim.objects.filter(
                    restaurant=self.restaurant,
                    status=self.STATUS_PENDING,
                )
                .exclude(pk=self.pk)
                .first()
            )
            if existing_for_restaurant:
                raise ValidationError(
                    "There is already a pending claim for this restaurant."
                )

    def approve(self, reviewer=None, notes=""):
        with transaction.atomic():
            claim = (
                RestaurantOwnershipClaim.objects.select_for_update()
                .select_related("restaurant", "claimant")
                .get(pk=self.pk)
            )
            if claim.status != self.STATUS_PENDING:
                raise ValidationError("Only pending claims can be approved.")

            existing_restaurant = (
                Restaurant.objects.filter(owner=claim.claimant)
                .exclude(pk=claim.restaurant_id)
                .first()
            )
            if existing_restaurant:
                raise ValidationError(
                    "Claimant already owns another restaurant profile."
                )
            if (
                claim.restaurant.owner_id
                and claim.restaurant.owner_id != claim.claimant_id
            ):
                raise ValidationError(
                    "Restaurant is already assigned to another owner."
                )

            claim.restaurant.owner = claim.claimant
            claim.restaurant.save(update_fields=["owner", "updated_at"])

            if hasattr(claim.claimant, "userprofile"):
                profile = claim.claimant.userprofile
                profile.is_approved = True
                profile.is_rejected = False
                profile.save(update_fields=["is_approved", "is_rejected"])

            claim.status = self.STATUS_APPROVED
            claim.reviewed_by = reviewer
            claim.reviewed_at = timezone.now()
            if notes:
                claim.review_notes = notes
            claim.save(
                update_fields=[
                    "status",
                    "reviewed_by",
                    "reviewed_at",
                    "review_notes",
                    "updated_at",
                ]
            )

            return claim

    def reject(self, reviewer=None, notes=""):
        if self.status != self.STATUS_PENDING:
            raise ValidationError("Only pending claims can be rejected.")
        self.status = self.STATUS_REJECTED
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        if notes:
            self.review_notes = notes
        self.save(
            update_fields=[
                "status",
                "reviewed_by",
                "reviewed_at",
                "review_notes",
                "updated_at",
            ]
        )
        return self


class RestaurantPhoto(models.Model):
    """
    Model to handle multiple photos for a restaurant.
    """

    restaurant = models.ForeignKey(
        Restaurant, on_delete=models.CASCADE, related_name="photos"
    )
    photo = models.ImageField(upload_to="restaurant_photos/")
    caption = models.CharField(max_length=255, blank=True, null=True)
    is_primary = models.BooleanField(
        default=False, help_text="Set as main photo for the restaurant"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_primary", "-uploaded_at"]

    def __str__(self):
        return f"{self.restaurant.name} - {self.caption or 'Photo'}"

    def save(self, *args, **kwargs):
        """Ensure only one primary photo"""
        if self.is_primary:
            # Remove primary status from other photos
            RestaurantPhoto.objects.filter(
                restaurant=self.restaurant, is_primary=True
            ).update(is_primary=False)
        super().save(*args, **kwargs)


class LoginLog(models.Model):
    """
    Tracks authentication events for simple login analytics and anti-abuse checks.
    """

    STATUS_CHOICES = [
        ("Success", "Success"),
        ("Failure", "Failure"),
    ]

    username = models.CharField(max_length=150, help_text="Attempted username")
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    user_agent = models.TextField(blank=True, null=True)
    is_suspicious = models.BooleanField(default=False)
    is_user_suspicious = models.BooleanField(default=False)
    user = models.ForeignKey(User, blank=True, null=True, on_delete=models.CASCADE)

    def __str__(self):
        target = self.user.username if self.user_id else self.username
        return f"{target} - {self.status}"


class RestaurantSourceRecord(models.Model):
    SOURCE_EATERIES = "EATERIES"
    SOURCE_DINING_OUT = "DINING_OUT"
    SOURCE_DOHMH = "DOHMH"

    SOURCE_CHOICES = [
        (SOURCE_EATERIES, "Directory of Eateries"),
        (SOURCE_DINING_OUT, "Dining Out NYC Locations"),
        (SOURCE_DOHMH, "DOHMH Restaurant Inspection Results"),
    ]

    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name="sources",
    )
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    external_id = models.CharField(max_length=200)
    external_name = models.CharField(max_length=255)
    external_address = models.CharField(max_length=255, blank=True, null=True)
    raw_payload = models.JSONField(blank=True, null=True)
    confidence = models.DecimalField(max_digits=4, decimal_places=3, default=0.0)
    source_url = models.URLField(max_length=500, blank=True, null=True)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [["source", "external_id"]]
        indexes = [
            models.Index(fields=["source", "external_id"], name="nomz_source_ext_1"),
            models.Index(fields=["restaurant", "source"], name="nomz_source_rest_2"),
        ]

    def __str__(self):
        return f"{self.source} {self.external_id}"


class DiningOutLocation(models.Model):
    LOCATION_TYPE_CHOICES = [
        ("indoor", "Indoor"),
        ("outdoor", "Outdoor"),
        ("sidewalk", "Sidewalk"),
        ("mixed", "Mixed"),
        ("unknown", "Unknown"),
    ]

    restaurant = models.OneToOneField(
        Restaurant,
        on_delete=models.CASCADE,
        related_name="dining_out_profile",
    )
    license_type = models.CharField(max_length=80, blank=True, null=True)
    license_status = models.CharField(max_length=80, blank=True, null=True)
    license_issue_date = models.DateField(blank=True, null=True)
    license_expiration_date = models.DateField(blank=True, null=True)
    location_type = models.CharField(
        max_length=20,
        choices=LOCATION_TYPE_CHOICES,
        default="unknown",
    )
    building_number = models.CharField(max_length=40, blank=True, null=True)
    council_district = models.CharField(max_length=20, blank=True, null=True)
    community_board = models.CharField(max_length=20, blank=True, null=True)
    nta2020 = models.CharField(max_length=32, blank=True, null=True)
    boro_code = models.CharField(max_length=20, blank=True, null=True)
    bin = models.CharField(max_length=40, blank=True, null=True)
    bbl = models.CharField(max_length=40, blank=True, null=True)
    capacity_estimate = models.IntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["restaurant"]),
            models.Index(fields=["license_type", "license_status"]),
        ]

    def __str__(self):
        return f"DiningOutProfile: {self.restaurant_id}"


class InspectionRecord(models.Model):
    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name="inspections",
    )
    inspection_date = models.DateField()
    inspection_key = models.CharField(max_length=200)
    grade = models.CharField(max_length=12, blank=True, null=True)
    score = models.IntegerField(blank=True, null=True)
    critical_violations = models.IntegerField(default=0)
    noncritical_violations = models.IntegerField(default=0)
    violation_count = models.IntegerField(default=0)
    inspection_type = models.CharField(max_length=128, blank=True, null=True)
    action = models.CharField(max_length=255, blank=True, null=True)
    violations = models.JSONField(default=list, blank=True)
    camis = models.CharField(max_length=80, blank=True, null=True)
    boro = models.CharField(max_length=80, blank=True, null=True)
    raw_payload = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [["restaurant", "inspection_key"]]
        indexes = [
            models.Index(
                fields=["restaurant", "inspection_date"], name="nomz_insp_rest_1"
            ),
            models.Index(fields=["grade"], name="nomz_insp_grade_1"),
        ]
        ordering = ["-inspection_date"]

    def __str__(self):
        return f"{self.restaurant_id}:{self.inspection_key}"


class DataIngestionRun(models.Model):
    STATUS_CHOICES = [
        ("running", "Running"),
        ("success", "Success"),
        ("failed", "Failed"),
    ]

    dataset = models.CharField(max_length=64)
    status = models.CharField(max_length=20, default="running", choices=STATUS_CHOICES)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(blank=True, null=True)
    records_fetched = models.IntegerField(default=0)
    records_processed = models.IntegerField(default=0)
    records_created = models.IntegerField(default=0)
    records_updated = models.IntegerField(default=0)
    records_matched = models.IntegerField(default=0)
    records_skipped = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    error_log = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.dataset} | {self.status} | {self.started_at:%Y-%m-%d %H:%M}"


class CompositeScoreHistory(models.Model):
    TRIGGER_SIGNAL_REVIEW = "signal_review"
    TRIGGER_SIGNAL_REVIEW_DELETE = "signal_review_delete"
    TRIGGER_SIGNAL_INSPECTION = "signal_inspection"
    TRIGGER_SIGNAL_INSPECTION_DELETE = "signal_inspection_delete"
    TRIGGER_ADMIN_ACTION = "admin_action"
    TRIGGER_ADMIN_DASHBOARD = "admin_dashboard"
    TRIGGER_MANAGEMENT_COMMAND = "management_command"
    TRIGGER_INGESTION = "ingestion"
    TRIGGER_OTHER = "other"

    TRIGGER_CHOICES = [
        (TRIGGER_SIGNAL_REVIEW, "Review Saved Signal"),
        (TRIGGER_SIGNAL_REVIEW_DELETE, "Review Deleted Signal"),
        (TRIGGER_SIGNAL_INSPECTION, "Inspection Saved Signal"),
        (TRIGGER_SIGNAL_INSPECTION_DELETE, "Inspection Deleted Signal"),
        (TRIGGER_ADMIN_ACTION, "Django Admin Action"),
        (TRIGGER_ADMIN_DASHBOARD, "Admin Dashboard"),
        (TRIGGER_MANAGEMENT_COMMAND, "Management Command"),
        (TRIGGER_INGESTION, "Ingestion Pipeline"),
        (TRIGGER_OTHER, "Other"),
    ]

    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name="score_history",
    )
    calculated_at = models.DateTimeField(auto_now_add=True, db_index=True)
    algorithm_version = models.CharField(max_length=32, default="v2")
    trigger_source = models.CharField(
        max_length=32,
        choices=TRIGGER_CHOICES,
        default=TRIGGER_OTHER,
        db_index=True,
    )
    trigger_note = models.CharField(max_length=255, blank=True, default="")
    triggered_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="composite_score_recalculations",
    )

    composite_score = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    previous_composite_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    delta_from_previous = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    grade = models.CharField(max_length=12, blank=True, default="")
    grade_score = models.IntegerField(default=0)
    last_inspection_date = models.DateField(blank=True, null=True)

    inspection_component_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=0
    )
    review_component_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=0
    )
    price_value_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    operational_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    review_count = models.IntegerField(default=0)
    review_confidence = models.DecimalField(max_digits=4, decimal_places=3, default=0)

    score_breakdown = models.JSONField(default=list, blank=True)
    score_inputs = models.JSONField(default=dict, blank=True)
    anomaly_flags = models.JSONField(default=list, blank=True)
    is_anomalous = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ["-calculated_at"]
        indexes = [
            models.Index(fields=["restaurant", "-calculated_at"]),
            models.Index(fields=["trigger_source", "-calculated_at"]),
            models.Index(fields=["is_anomalous", "-calculated_at"]),
        ]

    def __str__(self):
        return (
            f"{self.restaurant_id} score={self.composite_score} "
            f"({self.trigger_source}) @{self.calculated_at:%Y-%m-%d %H:%M}"
        )


class CompositeScoreAnomaly(models.Model):
    TYPE_LARGE_DELTA = "large_delta"
    TYPE_LOW_CONFIDENCE_HIGH_SCORE = "low_confidence_high_score"
    TYPE_STALE_INSPECTION_HIGH_SCORE = "stale_inspection_high_score"

    TYPE_CHOICES = [
        (TYPE_LARGE_DELTA, "Large Score Delta"),
        (TYPE_LOW_CONFIDENCE_HIGH_SCORE, "Low Confidence With High Score"),
        (TYPE_STALE_INSPECTION_HIGH_SCORE, "Stale Inspection With High Score"),
    ]

    SEVERITY_LOW = "LOW"
    SEVERITY_MEDIUM = "MEDIUM"
    SEVERITY_HIGH = "HIGH"
    SEVERITY_CRITICAL = "CRITICAL"
    SEVERITY_CHOICES = [
        (SEVERITY_LOW, "Low"),
        (SEVERITY_MEDIUM, "Medium"),
        (SEVERITY_HIGH, "High"),
        (SEVERITY_CRITICAL, "Critical"),
    ]

    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name="score_anomalies",
    )
    score_history = models.ForeignKey(
        CompositeScoreHistory,
        on_delete=models.CASCADE,
        related_name="anomalies",
    )
    anomaly_type = models.CharField(max_length=64, choices=TYPE_CHOICES, db_index=True)
    severity = models.CharField(
        max_length=16, choices=SEVERITY_CHOICES, default=SEVERITY_MEDIUM, db_index=True
    )
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    is_resolved = models.BooleanField(default=False, db_index=True)
    resolved_at = models.DateTimeField(blank=True, null=True)
    resolved_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="resolved_score_anomalies",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["restaurant", "is_resolved"]),
            models.Index(fields=["anomaly_type", "severity", "is_resolved"]),
        ]

    def __str__(self):
        return (
            f"{self.restaurant_id} {self.anomaly_type} "
            f"({'resolved' if self.is_resolved else 'open'})"
        )


# User preferences model to store diner preferences for personalized recommendations and search filtering


class UserPreference(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="preferences"
    )
    favorite_cuisines = models.JSONField(
        default=list, blank=True, help_text="List of preferred cuisines"
    )
    dietary_restrictions = models.JSONField(
        default=list, blank=True, help_text="e.g., Vegan, Gluten-Free"
    )
    price_preference = models.CharField(
        max_length=10, choices=Restaurant.PRICE_CHOICES, default="$$"
    )
    neighborhood_preference = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ===== NEW FIELDS FOR LEARNING =====
    # Dynamic preference weights (adjusted by learning algorithm)
    cuisine_weight = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=1.0,
        validators=[MinValueValidator(0.5), MaxValueValidator(2.0)],
        help_text="Weight multiplier for cuisine matching (0.5-2.0, adjusted by learning)",
    )

    dietary_weight = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=1.0,
        validators=[MinValueValidator(0.5), MaxValueValidator(2.0)],
        help_text="Weight multiplier for dietary restrictions matching",
    )

    price_weight = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=1.0,
        validators=[MinValueValidator(0.5), MaxValueValidator(2.0)],
        help_text="Weight multiplier for price range matching",
    )

    neighborhood_weight = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=1.0,
        validators=[MinValueValidator(0.5), MaxValueValidator(2.0)],
        help_text="Weight multiplier for neighborhood preference",
    )

    composite_score_weight = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=1.0,
        validators=[MinValueValidator(0.5), MaxValueValidator(2.0)],
        help_text="Weight multiplier for restaurant quality score",
    )

    historical_satisfaction_weight = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.5,
        validators=[MinValueValidator(0.0), MaxValueValidator(2.0)],
        help_text="Weight for historical user satisfaction with similar restaurants",
    )

    # Recommendation metrics
    total_recommendations_received = models.IntegerField(
        default=0, help_text="Total recommendations shown to this user"
    )

    successful_recommendations = models.IntegerField(
        default=0, help_text="Number of recommendations user interacted with"
    )

    # Tracking model iterations
    recommendation_model_version = models.IntegerField(
        default=1,
        help_text="Which version of recommendation model is being used for this user",
    )

    # Timestamps for learning
    last_recommendation_recalculated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time recommendations were calculated for this user",
    )

    last_recommendation_improvement_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time preference weights were improved by learning algorithm",
    )

    last_weights_adjustment_reason = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Reason why weights were last adjusted (for debugging)",
    )

    # Learning confidence
    learning_data_quality_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.0,
        help_text="Confidence in learned weights (0-100%)",
    )

    minimum_interactions_for_learning = models.IntegerField(
        default=3,
        help_text="Minimum number of interactions needed before weight adjustment",
    )

    class Meta:
        indexes = [
            models.Index(fields=["user", "-last_recommendation_recalculated_at"]),
            models.Index(fields=["recommendation_model_version"]),
        ]

    def __str__(self):
        return f"Preferences for {self.user.username} (v{self.recommendation_model_version})"

    @property
    def recommendation_success_rate(self):
        """Calculate percentage of recommendations that led to interaction"""
        if self.total_recommendations_received == 0:
            return 0.0
        return (
            self.successful_recommendations / self.total_recommendations_received
        ) * 100

    @property
    def all_weights_sum(self):
        """Verify weights are balanced"""
        return (
            self.cuisine_weight
            + self.dietary_weight
            + self.price_weight
            + self.neighborhood_weight
            + self.composite_score_weight
            + self.historical_satisfaction_weight
        )

    def reset_learning_weights(self):
        """Reset all learned weights back to defaults"""
        self.cuisine_weight = 1.0
        self.dietary_weight = 1.0
        self.price_weight = 1.0
        self.neighborhood_weight = 1.0
        self.composite_score_weight = 1.0
        self.historical_satisfaction_weight = 0.5
        self.recommendation_model_version += 1
        self.learning_data_quality_score = 0.0
        self.save()

    def has_enough_data_for_learning(self):
        """Check if user has enough interaction history for meaningful learning"""
        interaction_count = self.user.interaction_history.count()
        return interaction_count >= self.minimum_interactions_for_learning


class UserInteractionHistory(models.Model):
    """
    Tracks all user interactions with restaurants to build historical context
    for machine learning and continuous recommendation refinement.
    """

    INTERACTION_TYPES = [
        ("view", "Restaurant View"),
        ("profile_view", "Profile Page View"),
        ("search", "Search Query"),
        ("review_submitted", "Review Submitted"),
        ("rating_given", "Rating Provided"),
        ("recommendation_viewed", "Recommendation Viewed"),
        ("recommendation_clicked", "Recommendation Clicked"),
        ("reservation", "Reservation Made"),
        ("menu_viewed", "Menu Viewed"),
        ("photo_viewed", "Photos Viewed"),
        ("contact_clicked", "Contact Info Clicked"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="interaction_history"
    )
    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name="user_interactions",
        null=True,
        blank=True,
    )

    # Interaction metadata
    interaction_type = models.CharField(max_length=50, choices=INTERACTION_TYPES)

    # Optional: search query if interaction_type='search'
    search_query = models.CharField(max_length=500, blank=True, null=True)

    # User satisfaction metrics (populated for review_submitted interactions)
    satisfaction_score = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(-1), MaxValueValidator(5)],
        help_text="User satisfaction: -1=bad, 0=neutral, 1-5=rating scale",
    )

    # Time spent on page/section (in seconds)
    time_spent_seconds = models.IntegerField(null=True, blank=True)

    # Engagement metrics
    was_shared = models.BooleanField(
        default=False, help_text="Did user share this restaurant?"
    )
    was_saved = models.BooleanField(
        default=False, help_text="Did user save/favorite this restaurant?"
    )
    was_recommended = models.BooleanField(
        default=False, help_text="Was this a recommended restaurant shown to user?"
    )
    recommendation_rank = models.IntegerField(
        null=True,
        blank=True,
        help_text="Position in recommendation list (1=first, 2=second, etc)",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=False, default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"], name="userinteract_user_date"),
            models.Index(
                fields=["restaurant", "-created_at"], name="userinteract_rest_date"
            ),
            models.Index(
                fields=["user", "restaurant", "-created_at"],
                name="userinteract_user_rest_date",
            ),
            models.Index(
                fields=["interaction_type", "-created_at"],
                name="userinteract_type_date",
            ),
        ]
        verbose_name = "User Interaction History"
        verbose_name_plural = "User Interaction Histories"

    def __str__(self):
        return f"{self.user.username} - {self.get_interaction_type_display()} - {self.created_at}"

    @property
    def days_since_interaction(self):
        """Calculate days since this interaction occurred"""
        return (timezone.now() - self.created_at).days

    @property
    def interaction_weight(self):
        """
        Calculate time-based weight for this interaction.
        Recent = higher weight, older = lower weight
        """
        days_old = self.days_since_interaction
        if days_old <= 30:
            return 2.0  # Recent activity (last 30 days)
        elif days_old <= 90:
            return 1.5  # Medium-term (30-90 days)
        else:
            return 1.0  # Older activity


class RecalculatedRecommendation(models.Model):
    """
    Stores recommendation snapshots to track model accuracy and learn from outcomes.
    Helps measure whether recommendations lead to user interactions and satisfaction.
    """

    ACCURACY_CHOICES = [
        (1, "Great Match - User Loved It"),
        (0, "Okay Match - User Indifferent"),
        (-1, "Poor Match - User Disliked It"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="calculated_recommendations"
    )
    restaurant = models.ForeignKey(
        Restaurant, on_delete=models.CASCADE, related_name="calculated_for_users"
    )

    # Score at time of recommendation
    recommendation_score = models.DecimalField(max_digits=5, decimal_places=2)

    # Component scores for analysis
    cuisine_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    price_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    dietary_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    neighborhood_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    quality_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    historical_satisfaction_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )

    # Learning/Accuracy metrics
    accuracy_feedback = models.IntegerField(
        null=True,
        blank=True,
        choices=ACCURACY_CHOICES,
        help_text="Manual or inferred feedback on recommendation quality",
    )

    # Interaction tracking
    user_interacted = models.BooleanField(
        default=False, help_text="Did user click/view this recommended restaurant?"
    )
    days_to_interaction = models.IntegerField(
        null=True,
        blank=True,
        help_text="Days until user interacted with this restaurant",
    )
    interaction_type = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Type of interaction (view, review, reservation, etc)",
    )
    recommendation_rank = models.IntegerField(
        null=True,
        blank=True,
        help_text="Position in recommendation list at time of generation",
    )

    # Timestamps
    calculated_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    interaction_detected_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-calculated_at"]
        indexes = [
            models.Index(fields=["user", "-calculated_at"], name="rec_user_date"),
            models.Index(
                fields=["user_interacted", "-calculated_at"], name="rec_interacted_date"
            ),
            models.Index(
                fields=["accuracy_feedback", "-created_at"], name="rec_accuracy_date"
            ),
        ]
        verbose_name = "Recalculated Recommendation"
        verbose_name_plural = "Recalculated Recommendations"

    def __str__(self):
        return f"Rec: {self.user.username} → {self.restaurant.name} (score: {self.recommendation_score})"

    @property
    def is_accurate(self):
        """Returns True if recommendation was accurate (user interacted positively)"""
        return self.accuracy_feedback in [1, 0]  # Great or okay, not poor

    def calculate_accuracy_from_interactions(self):
        """
        Automatically infer accuracy based on user interactions after recommendation.
        Call this periodically to update accuracy_feedback.
        """
        # Check if user reviewed this restaurant after recommendation
        recent_review = self.user.reviews.filter(
            restaurant=self.restaurant,
            created_at__gte=self.calculated_at,
            is_deleted=False,
        ).first()

        if recent_review:
            self.interaction_type = "review_submitted"
            self.user_interacted = True
            self.interaction_detected_at = recent_review.created_at
            self.days_to_interaction = (
                recent_review.created_at - self.calculated_at
            ).days

            # Infer accuracy from review rating
            if recent_review.rating >= 4:
                self.accuracy_feedback = 1
            elif recent_review.rating >= 3:
                self.accuracy_feedback = 0
            else:
                self.accuracy_feedback = -1

            self.save(
                update_fields=[
                    "user_interacted",
                    "interaction_type",
                    "interaction_detected_at",
                    "days_to_interaction",
                    "accuracy_feedback",
                ]
            )
            return

        # Check if user viewed this restaurant after recommendation
        recent_view = self.user.interaction_history.filter(
            restaurant=self.restaurant,
            interaction_type__in=["view", "profile_view"],
            created_at__gte=self.calculated_at,
        ).first()

        if recent_view:
            self.interaction_type = "view"
            self.user_interacted = True
            self.interaction_detected_at = recent_view.created_at
            self.days_to_interaction = (
                recent_view.created_at - self.calculated_at
            ).days
            self.accuracy_feedback = 0  # Neutral - just viewed
            self.save(
                update_fields=[
                    "user_interacted",
                    "interaction_type",
                    "interaction_detected_at",
                    "days_to_interaction",
                    "accuracy_feedback",
                ]
            )


class RecommendationModelMetric(models.Model):
    """
    Tracks system-wide recommendation quality metrics daily.
    Helps monitor whether the continuous refinement is improving recommendations.
    """

    metric_date = models.DateField(auto_now_add=True)

    # Volume metrics
    total_recommendations_given = models.IntegerField(default=0)
    total_users_with_recommendations = models.IntegerField(default=0)

    # Accuracy metrics
    successful_recommendations = models.IntegerField(
        default=0, help_text="Number of recommendations that led to user interaction"
    )
    avg_recommendation_accuracy = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Percentage (0-100) of recommendations leading to interaction",
    )

    # Interaction timing
    avg_days_to_interaction = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Average days between recommendation and user interaction",
    )

    # Success rates by preference type
    cuisine_match_success_rate = models.DecimalField(
        max_digits=5, decimal_places=2, null=True
    )
    price_match_success_rate = models.DecimalField(
        max_digits=5, decimal_places=2, null=True
    )
    dietary_match_success_rate = models.DecimalField(
        max_digits=5, decimal_places=2, null=True
    )
    neighborhood_match_success_rate = models.DecimalField(
        max_digits=5, decimal_places=2, null=True
    )

    # Model quality
    avg_recommendation_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True
    )
    recommendations_with_perfect_score = models.IntegerField(default=0)

    # Learning indicators
    recommendations_updated_from_learning = models.IntegerField(
        default=0,
        help_text="How many recommendation weights were adjusted based on learning",
    )
    users_with_improved_weights = models.IntegerField(
        default=0,
        help_text="Number of users whose preference weights improved accuracy",
    )

    last_recalculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-metric_date"]
        indexes = [
            models.Index(fields=["-metric_date"], name="metric_date_idx"),
        ]
        verbose_name = "Recommendation Model Metric"
        verbose_name_plural = "Recommendation Model Metrics"

    def __str__(self):
        return f"Recommendation Metrics - {self.metric_date} (Accuracy: {self.avg_recommendation_accuracy}%)"

    @property
    def month_over_month_improvement(self):
        """Calculate month-over-month accuracy improvement"""
        from datetime import timedelta

        prev_month = self.metric_date - timedelta(days=30)
        prev_metric = (
            RecommendationModelMetric.objects.filter(metric_date__lte=prev_month)
            .order_by("-metric_date")
            .first()
        )

        if not prev_metric or not prev_metric.avg_recommendation_accuracy:
            return None

        if not self.avg_recommendation_accuracy:
            return None

        improvement = float(self.avg_recommendation_accuracy) - float(
            prev_metric.avg_recommendation_accuracy
        )
        return improvement


class SystemAuditLog(models.Model):
    """
    System-wide audit trail for critical administrative and platform events.
    """

    LEVEL_CHOICES = [
        ("INFO", "Info"),
        ("WARNING", "Warning"),
        ("ERROR", "Error"),
        ("CRITICAL", "Critical"),
    ]

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    actor_user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="system_audit_logs",
    )
    actor_username = models.CharField(max_length=150, blank=True, default="")

    level = models.CharField(
        max_length=10, choices=LEVEL_CHOICES, default="INFO", db_index=True
    )
    action = models.CharField(max_length=255, db_index=True)

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)

    request_path = models.CharField(max_length=2048, null=True, blank=True)
    http_method = models.CharField(max_length=10, null=True, blank=True)

    # Free-form event details (avoid huge stack traces; keep structured info).
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        actor = self.actor_username or (
            self.actor_user.username if self.actor_user_id else "anonymous"
        )
        return f"{self.level} {self.action} ({actor})"


class SystemPerformanceMetric(models.Model):
    """
    Per-request performance/error metrics used for dashboards and alert evaluation.
    """

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    # request identification
    method = models.CharField(max_length=10, db_index=True)
    path = models.CharField(max_length=2048, db_index=True)

    # performance/error details
    duration_ms = models.PositiveIntegerField()
    status_code = models.PositiveIntegerField(db_index=True)
    is_error = models.BooleanField(default=False, db_index=True)

    exception_class = models.CharField(max_length=255, blank=True, default="")
    exception_message = models.CharField(max_length=500, blank=True, default="")

    class Meta:
        indexes = [
            models.Index(
                fields=["created_at", "is_error"], name="nomz_sysperf_err_idx"
            ),
            models.Index(
                fields=["created_at", "duration_ms"], name="nomz_sysperf_lat_idx"
            ),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.method} {self.path} {self.status_code} ({self.duration_ms}ms)"


class SystemPerformanceSnapshot(models.Model):
    """
    Aggregated snapshot over a fixed time bucket for quick admin visibility.
    """

    interval_start = models.DateTimeField(db_index=True)
    interval_end = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    total_requests = models.IntegerField()
    error_requests = models.IntegerField()
    error_rate = models.DecimalField(max_digits=6, decimal_places=4)

    avg_latency_ms = models.DecimalField(max_digits=10, decimal_places=2)
    max_latency_ms = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        unique_together = [("interval_start", "interval_end")]
        ordering = ["-interval_end"]

    def __str__(self):
        return f"{self.interval_start:%Y-%m-%d %H:%M:%S} - {self.interval_end:%H:%M:%S}"


class SystemAlert(models.Model):
    """
    Alert records generated from snapshot evaluation or health-check failures.
    """

    ALERT_TYPE_CHOICES = [
        ("HEALTH_CHECK_FAILURE", "Health check failure"),
        ("HIGH_ERROR_RATE", "High error rate"),
        ("HIGH_LATENCY", "High latency"),
    ]

    SEVERITY_CHOICES = [
        ("LOW", "Low"),
        ("MEDIUM", "Medium"),
        ("HIGH", "High"),
        ("CRITICAL", "Critical"),
    ]

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    alert_type = models.CharField(
        max_length=64, choices=ALERT_TYPE_CHOICES, db_index=True
    )
    severity = models.CharField(
        max_length=16, choices=SEVERITY_CHOICES, default="HIGH", db_index=True
    )

    message = models.CharField(max_length=500)
    details = models.JSONField(default=dict, blank=True)

    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.alert_type} ({self.severity}) - {'active' if self.is_active else 'resolved'}"


class Review(models.Model):
    """
    Model for users to leave reviews for restaurants.
    """

    restaurant = models.ForeignKey(
        Restaurant, on_delete=models.CASCADE, related_name="reviews"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField(
        help_text="Overall rating from 1 to 5",
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    food_quality_rating = models.PositiveSmallIntegerField(
        default=4,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Food quality rating from 1 to 5",
    )
    service_quality_rating = models.PositiveSmallIntegerField(
        default=4,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Service quality rating from 1 to 5",
    )
    ambience_rating = models.PositiveSmallIntegerField(
        default=4,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Ambience rating from 1 to 5",
    )
    location_rating = models.PositiveSmallIntegerField(
        default=4,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Location and accessibility rating from 1 to 5",
    )
    value_rating = models.PositiveSmallIntegerField(
        default=4,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Price-to-value rating from 1 to 5",
    )
    dietary_accommodation_rating = models.PositiveSmallIntegerField(
        default=4,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Dietary accommodation quality rating from 1 to 5",
    )
    cleanliness_rating = models.PositiveSmallIntegerField(
        default=4,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Cleanliness rating from 1 to 5",
    )
    comment = models.TextField(blank=True, null=True)
    is_flagged = models.BooleanField(
        default=False, help_text="Flagged for moderation/fraud"
    )
    is_deleted = models.BooleanField(default=False, help_text="Soft delete for reviews")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Review by {self.user.username} for {self.restaurant.name} ({self.rating}/5)"

    @property
    def experience_rating(self):
        weighted = (
            (self.food_quality_rating * 0.30)
            + (self.service_quality_rating * 0.20)
            + (self.ambience_rating * 0.15)
            + (self.location_rating * 0.10)
            + (self.value_rating * 0.10)
            + (self.dietary_accommodation_rating * 0.05)
            + (self.cleanliness_rating * 0.10)
        )
        return round(weighted, 2)


class ReviewResponse(models.Model):
    """
    Public response from a restaurant owner to a specific review.
    Exactly one response is allowed per review.
    """

    review = models.OneToOneField(
        Review,
        on_delete=models.CASCADE,
        related_name="restaurant_response",
    )
    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name="review_responses",
    )
    responder = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="review_responses",
    )
    response_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Response by {self.responder.username} to review {self.review_id}"

    def clean(self):
        if self.review_id and self.restaurant_id != self.review.restaurant_id:
            raise ValidationError(
                "Review response restaurant does not match the review's restaurant."
            )
        if self.restaurant_id and self.responder_id:
            if self.restaurant.owner_id != self.responder_id:
                raise ValidationError(
                    "Only the restaurant owner can submit a public response."
                )


class Conversation(models.Model):
    """
    One-to-one messaging thread between a restaurant owner and a diner.
    """

    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name="conversations",
    )
    diner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="diner_conversations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("restaurant", "diner")]
        indexes = [
            models.Index(fields=["restaurant", "updated_at"]),
            models.Index(fields=["diner", "updated_at"]),
        ]
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.restaurant.name} <-> {self.diner.username}"

    def can_access(self, user):
        if not user or not user.is_authenticated:
            return False
        return self.diner_id == user.id or self.restaurant.owner_id == user.id


class Message(models.Model):
    """
    Individual message belonging to a conversation.
    """

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sent_messages",
    )
    body = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["conversation", "created_at"]),
            models.Index(fields=["sender", "created_at"]),
        ]
        ordering = ["created_at"]

    def __str__(self):
        return f"Message {self.id} by {self.sender.username}"


class MessageNotification(models.Model):
    """
    Notification for a newly received message.
    """

    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="message_notifications",
    )
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    message = models.OneToOneField(
        Message,
        on_delete=models.CASCADE,
        related_name="notification",
    )
    triggered_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="triggered_message_notifications",
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["recipient", "is_read", "created_at"]),
            models.Index(fields=["recipient", "conversation", "is_read"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"Notification for {self.recipient.username} on message {self.message_id}"
        )


class ModerationReport(models.Model):
    """
    Tracks reports made by users against reviews or other user accounts.
    """

    REASON_CHOICES = [
        ("SPAM", "Spam or misleading"),
        ("FRAUD", "Fraudulent activity"),
        ("HARASSMENT", "Harassment or hate speech"),
        ("INAPPROPRIATE", "Inappropriate content"),
        ("OTHER", "Other"),
    ]

    STATUS_CHOICES = [
        ("PENDING", "Pending Review"),
        ("RESOLVED", "Resolved (Action Taken)"),
        ("DISMISSED", "Dismissed (No Action)"),
    ]

    reporter = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="reports_made"
    )
    # A report can be against a specific review OR a user profile
    review = models.ForeignKey(
        Review, on_delete=models.SET_NULL, null=True, blank=True, related_name="reports"
    )
    reported_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reports_received",
    )

    reason = models.CharField(max_length=50, choices=REASON_CHOICES, default="other")
    details = models.TextField(help_text="Additional information about the report")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")

    # Tracking moderation actions
    moderator_note = models.TextField(blank=True, null=True)
    action_taken = models.CharField(max_length=100, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        target = (
            f"Review {self.review_id}" if self.review else f"User {self.reported_user}"
        )
        return f"Report by {self.reporter.username} on {target} ({self.status})"


class FriendConversation(models.Model):
    """
    A conversation between two or more users.
    Can be a 1-on-1 chat or a group chat.
    """

    # Participants in the conversation
    participants = models.ManyToManyField(User, related_name="friend_chats", blank=True)

    # Metadata for group chats
    name = models.CharField(max_length=255, null=True, blank=True)
    is_group = models.BooleanField(default=False)
    creator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_group_chats",
    )

    # Legacy fields (retained to avoid breaking existing data immediately)
    user1 = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="friend_conversations_initiated_legacy",
        null=True,
        blank=True,
    )
    user2 = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="friend_conversations_received_legacy",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        if self.is_group and self.name:
            return f"Group: {self.name}"
        return f"Chat: {', '.join([u.username for u in self.get_participants()])}"

    def get_participants(self):
        """Returns all participants, falling back to legacy fields if M2M not yet populated."""
        parts = self.participants.all()
        if parts.exists():
            return parts
        # If participants M2M is empty, return user1 and user2
        return User.objects.filter(id__in=[self.user1_id, self.user2_id]).filter(
            id__isnull=False
        )

    def can_access(self, user):
        if not user or not user.is_authenticated:
            return False
        return self.get_participants().filter(id=user.id).exists()


class FriendMessage(models.Model):
    """
    Individual message belonging to a FriendConversation.
    """

    conversation = models.ForeignKey(
        FriendConversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sent_friend_messages",
    )
    body = models.TextField(blank=True, null=True)
    restaurant_recommendation = models.ForeignKey(
        "Restaurant", on_delete=models.SET_NULL, null=True, blank=True
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"FriendMessage by {self.sender.username} at {self.created_at}"


class FriendSharedRestaurant(models.Model):
    """
    Restaurants that friends in a conversation have added to their 'Together List'.
    """

    conversation = models.ForeignKey(
        FriendConversation,
        on_delete=models.CASCADE,
        related_name="shared_restaurants",
    )
    restaurant = models.ForeignKey("Restaurant", on_delete=models.CASCADE)
    added_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("conversation", "restaurant")]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.restaurant.name} in {self.conversation}"
