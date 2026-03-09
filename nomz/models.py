from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.db import models


class UserProfile(models.Model):
    id = models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')

    ROLE_CHOICES = [
        ('diner', 'Diner'),
        ('restaurant', 'Restaurant'),
    ]

    # Links this profile to the built-in Django User
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='diner')

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
        ('american', 'American'),
        ('asian', 'Asian'),
        ('italian', 'Italian'),
        ('mexican', 'Mexican'),
        ('indian', 'Indian'),
        ('french', 'French'),
        ('japanese', 'Japanese'),
        ('chinese', 'Chinese'),
        ('thai', 'Thai'),
        ('mediterranean', 'Mediterranean'),
        ('fusion', 'Fusion'),
        ('vegetarian', 'Vegetarian'),
        ('vegan', 'Vegan'),
        ('other', 'Other'),
    ]

    PRICE_CHOICES = [
        ('$', 'Budget-Friendly ($)'),
        ('$$', 'Moderate ($$)'),
        ('$$$', 'Upscale ($$$)'),
        ('$$$$', 'Fine Dining ($$$$)'),
    ]

    LOCATION_TYPE_CHOICES = [
        ('indoor', 'Indoor'),
        ('outdoor', 'Outdoor'),
        ('sidewalk', 'Sidewalk'),
        ('mixed', 'Mixed'),
        ('unknown', 'Unknown'),
    ]

    # Owner and basic owner-editable info
    owner = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='restaurant_profile',
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True, help_text='Describe your restaurant, cuisine style, and ambiance')
    address = models.CharField(max_length=500, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    email = models.EmailField(max_length=254, blank=True, null=True)
    cuisine_type = models.CharField(max_length=50, choices=CUISINE_CHOICES, default='other')
    price_range = models.CharField(max_length=10, choices=PRICE_CHOICES, default='$$')

    # Operating hours
    days_of_week = [
        ('MON', 'Monday'),
        ('TUE', 'Tuesday'),
        ('WED', 'Wednesday'),
        ('THU', 'Thursday'),
        ('FRI', 'Friday'),
        ('SAT', 'Saturday'),
        ('SUN', 'Sunday'),
    ]

    # Hours stored as JSONField for flexibility (optional: can use TimeField pairs)
    hours_open = models.TimeField(default='09:00', help_text='Opening time')
    hours_close = models.TimeField(default='21:00', help_text='Closing time')

    # Status and availability
    is_active = models.BooleanField(default=True, help_text='Profile is visible to customers')
    is_temporarily_unavailable = models.BooleanField(default=False, help_text='Temporarily mark as unavailable')
    unavailable_reason = models.CharField(max_length=500, blank=True, null=True)
    unavailable_until = models.DateTimeField(blank=True, null=True)

    # Legacy compatibility fields expected by existing views/admin/forms
    neighborhood = models.CharField(max_length=100, blank=True, default='')
    cuisine = models.CharField(max_length=100, blank=True, default='')

    # Ingestion-friendly normalized profile fields
    display_name = models.CharField(max_length=255, blank=True, default='')
    name_normalized = models.CharField(max_length=255, db_index=True, blank=True, default='')
    building = models.CharField(max_length=64, blank=True, null=True)
    street = models.CharField(max_length=255, blank=True, null=True)
    borough = models.CharField(max_length=80, blank=True, null=True)
    zip_code = models.CharField(max_length=10, db_index=True, blank=True, null=True)
    cuisine_tags = models.JSONField(default=list, blank=True)

    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)

    composite_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
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


class RestaurantPhoto(models.Model):
    """
    Model to handle multiple photos for a restaurant.
    """
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='photos')
    photo = models.ImageField(upload_to='restaurant_photos/')
    caption = models.CharField(max_length=255, blank=True, null=True)
    is_primary = models.BooleanField(default=False, help_text='Set as main photo for the restaurant')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_primary', '-uploaded_at']

    def __str__(self):
        return f"{self.restaurant.name} - {self.caption or 'Photo'}"

    def save(self, *args, **kwargs):
        """Ensure only one primary photo"""
        if self.is_primary:
            # Remove primary status from other photos
            RestaurantPhoto.objects.filter(restaurant=self.restaurant, is_primary=True).update(is_primary=False)
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
            models.Index(fields=["restaurant", "inspection_date"], name="nomz_insp_rest_1"),
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
