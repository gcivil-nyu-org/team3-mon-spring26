from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.db.models import Q
from .models import (
    UserProfile,
    Restaurant,
    RestaurantOwnershipClaim,
    RestaurantPhoto,
    ReviewResponse,
    UserPreference,
    Review,
    ModerationReport,
)


class UserRegisterForm(UserCreationForm):
    """
    Custom user registration form that extends Django's UserCreationForm.
    Adds email field and improves styling.
    """

    # Add the Role selection field
    ROLE_CHOICES = [
        ("diner", "I am a Diner"),
        ("restaurant", "I am a Restaurant Owner"),
    ]
    role = forms.ChoiceField(
        choices=ROLE_CHOICES, widget=forms.Select(attrs={"class": "form-control"})
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(
            attrs={"class": "form-control", "placeholder": "Email address"}
        ),
    )
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Username"}
        ),
    )
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "Password"}
        ),
    )
    password2 = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "Confirm password"}
        ),
    )

    class Meta:
        model = User
        fields = ["email", "username", "role", "password1", "password2"]

    def clean_email(self):
        """Ensure email is unique"""
        email = self.cleaned_data.get("email")
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already registered.")
        return email

    def save(self, commit=True):
        """Save user with email AND create their UserProfile"""
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
            # This is where the backend permanently stores the role!
            # Restaurant accounts start as NOT approved pending admin review (Issue #53)
            is_approved = self.cleaned_data["role"] != "restaurant"
            UserProfile.objects.create(
                user=user, role=self.cleaned_data["role"], is_approved=is_approved
            )
        return user


class UserLoginForm(AuthenticationForm):
    """
    Custom login form that extends Django's AuthenticationForm.
    Adds Bootstrap styling for better UI.
    """

    username = forms.CharField(
        max_length=254,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Username or Email"}
        ),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "Password"}
        )
    )


class AdminLoginForm(UserLoginForm):
    """
    Login form for administrators with an extra security code field.
    """

    security_code = forms.CharField(
        max_length=20,
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "Security Code"}
        ),
        help_text="Enter the administrative security code.",
    )

    def clean(self):
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")
        security_code = self.cleaned_data.get("security_code")

        # Hardcoded admin username, but the password is a secure hash so it is safe for GitHub
        HARDCODED_USER = "admin"
        HARDCODED_PASS_HASH = "pbkdf2_sha256$600000$NvKgdMfTjHfGXwLuieCtCo$r3maZLapzui28vRpgClLYsUaBjSjBsyyBunVvCEoVNc="

        self.user_cache = None

        from django.contrib.auth.hashers import check_password

        if username == HARDCODED_USER and check_password(password, HARDCODED_PASS_HASH):
            from django.contrib.auth.models import User

            user, created = User.objects.get_or_create(username=HARDCODED_USER)
            if (
                created
                or not user.is_staff
                or not user.is_superuser
                or user.password != HARDCODED_PASS_HASH
            ):
                user.password = HARDCODED_PASS_HASH
                user.is_staff = True
                user.is_superuser = True
                user.is_active = True
                user.save()

            # Required by Django's login() function when bypassing standard authenticate()
            user.backend = "django.contrib.auth.backends.ModelBackend"
            self.user_cache = user
        else:
            raise self.get_invalid_login_error()

        # Simple security code check
        # Reading from .env for security (Issue #46)
        from decouple import config

        expected_code = config("ADMIN_SECURITY_CODE", default="ADM123")

        if security_code != expected_code:
            raise forms.ValidationError("Invalid security code.")

        # Final verification that the user's status allows them to log in
        if self.user_cache is not None:
            self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data


class RestaurantProfileForm(forms.ModelForm):
    """
    Form for restaurant owners to create and edit their restaurant profile.
    Handles description, hours, cuisine type, and price range.
    """

    class Meta:
        model = Restaurant
        fields = [
            "name",
            "description",
            "cuisine_type",
            "price_range",
            "hours_open",
            "hours_close",
            "address",
            "phone",
            "website",
            "email",
        ]
        labels = {
            "name": "Restaurant Name",
            "description": "Description & Ambiance",
            "cuisine_type": "Cuisine Type",
            "price_range": "Price Range",
            "hours_open": "Opening Time",
            "hours_close": "Closing Time",
            "address": "Address",
            "phone": "Phone Number",
            "website": "Website",
            "email": "Contact Email",
        }
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": 'e.g., "The Italian Corner"',
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Describe your restaurant, cuisine style, and special offerings...",
                }
            ),
            "cuisine_type": forms.Select(attrs={"class": "form-control"}),
            "price_range": forms.Select(attrs={"class": "form-control"}),
            "hours_open": forms.TimeInput(
                attrs={"class": "form-control", "type": "time"}
            ),
            "hours_close": forms.TimeInput(
                attrs={"class": "form-control", "type": "time"}
            ),
            "address": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": 'e.g., "123 Main St, New York, NY 10001"',
                }
            ),
            "phone": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "(123) 456-7890"}
            ),
            "website": forms.URLInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "https://www.example.com",
                }
            ),
            "email": forms.EmailInput(
                attrs={"class": "form-control", "placeholder": "contact@restaurant.com"}
            ),
        }


class RestaurantAvailabilityForm(forms.ModelForm):
    """
    Form for restaurant owners to mark temporary unavailability.
    """

    class Meta:
        model = Restaurant
        fields = [
            "is_temporarily_unavailable",
            "unavailable_reason",
            "unavailable_until",
        ]
        labels = {
            "is_temporarily_unavailable": "Mark as Temporarily Unavailable",
            "unavailable_reason": "Reason for Unavailability",
            "unavailable_until": "Available Again On",
        }
        widgets = {
            "is_temporarily_unavailable": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "unavailable_reason": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "e.g., Renovations, Special Event, Staffing Issues...",
                }
            ),
            "unavailable_until": forms.DateTimeInput(
                attrs={"class": "form-control", "type": "datetime-local"}
            ),
        }


class RestaurantActivationForm(forms.ModelForm):
    """
    Form for restaurant owners to activate/deactivate their profile.
    """

    class Meta:
        model = Restaurant
        fields = ["is_active"]
        labels = {
            "is_active": "Profile Active & Visible to Customers",
        }
        widgets = {
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class RestaurantPhotoForm(forms.ModelForm):
    """
    Form for uploading restaurant photos.
    """

    class Meta:
        model = RestaurantPhoto
        fields = ["photo", "caption", "is_primary"]
        labels = {
            "photo": "Photo",
            "caption": "Photo Caption",
            "is_primary": "Set as Main Photo",
        }
        widgets = {
            "photo": forms.FileInput(
                attrs={"class": "form-control", "accept": "image/*"}
            ),
            "caption": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": 'e.g., "Dining Area", "Signature Dish"',
                }
            ),
            "is_primary": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class UserPreferenceForm(forms.ModelForm):
    # Defining choices manually or pulling from Restaurant.CUISINE_CHOICES
    CUISINE_OPTIONS = Restaurant.CUISINE_CHOICES
    DIETARY_CHOICES = [
        ("Vegan", "Vegan"),
        ("Vegetarian", "Vegetarian"),
        ("Non-vegetarian", "Non-vegetarian"),
        ("Gluten-Free", "Gluten-Free"),
        ("Halal", "Halal"),
        ("Kosher", "Kosher"),
    ]

    favorite_cuisines = forms.MultipleChoiceField(
        choices=CUISINE_OPTIONS, widget=forms.CheckboxSelectMultiple, required=False
    )
    dietary_restrictions = forms.MultipleChoiceField(
        choices=DIETARY_CHOICES, widget=forms.CheckboxSelectMultiple, required=False
    )

    class Meta:
        model = UserPreference
        fields = [
            "favorite_cuisines",
            "dietary_restrictions",
            "price_preference",
            "neighborhood_preference",
        ]


class RestaurantOwnershipClaimForm(forms.ModelForm):
    restaurant = forms.ModelChoiceField(
        queryset=Restaurant.objects.none(),
        widget=forms.Select(attrs={"class": "form-control"}),
        help_text="Pick your restaurant from the existing database records.",
    )

    class Meta:
        model = RestaurantOwnershipClaim
        fields = ["restaurant", "business_email", "contact_phone", "proof_details"]
        labels = {
            "business_email": "Business Email",
            "contact_phone": "Business Phone",
            "proof_details": "Verification Details",
        }
        widgets = {
            "business_email": forms.EmailInput(
                attrs={"class": "form-control", "placeholder": "owner@restaurant.com"}
            ),
            "contact_phone": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "+1 212-555-1234"}
            ),
            "proof_details": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Share proof like website manager email match, business license number, menu system access, or public listing links.",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        search_query = (kwargs.pop("search_query", "") or "").strip()
        super().__init__(*args, **kwargs)

        queryset = Restaurant.objects.filter(owner__isnull=True)
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query)
                | Q(address__icontains=search_query)
                | Q(zip_code__icontains=search_query)
            )

        self.fields["restaurant"].queryset = queryset.order_by("name")[:100]

        selected_restaurant_id = self.data.get("restaurant") or self.initial.get(
            "restaurant"
        )
        if selected_restaurant_id:
            self.fields["restaurant"].queryset = Restaurant.objects.filter(
                Q(owner__isnull=True) | Q(pk=selected_restaurant_id)
            ).order_by("name")

    def clean(self):
        cleaned_data = super().clean()
        restaurant = cleaned_data.get("restaurant")
        if not self.user or not restaurant:
            return cleaned_data

        if Restaurant.objects.filter(owner=self.user).exists():
            raise forms.ValidationError("You already own a restaurant profile.")

        if restaurant.owner and restaurant.owner != self.user:
            raise forms.ValidationError(
                "This restaurant is already owned by another user."
            )

        existing_claim = RestaurantOwnershipClaim.objects.filter(
            claimant=self.user,
            restaurant=restaurant,
            status=RestaurantOwnershipClaim.STATUS_PENDING,
        ).exists()
        if existing_claim:
            raise forms.ValidationError(
                "You already submitted a pending claim for this restaurant."
            )

        other_pending = RestaurantOwnershipClaim.objects.filter(
            claimant=self.user,
            status=RestaurantOwnershipClaim.STATUS_PENDING,
        ).exists()
        if other_pending:
            raise forms.ValidationError(
                "You already have another pending ownership claim."
            )

        restaurant_pending = RestaurantOwnershipClaim.objects.filter(
            restaurant=restaurant,
            status=RestaurantOwnershipClaim.STATUS_PENDING,
        ).exists()
        if restaurant_pending:
            raise forms.ValidationError(
                "This restaurant already has a pending claim under review."
            )

        return cleaned_data

    def save(self, commit=True):
        claim = super().save(commit=False)
        claim.claimant = self.user
        if commit:
            claim.save()
        return claim


class ReviewForm(forms.ModelForm):
    """
    Form for users to submit reviews for a restaurant.
    """

    class Meta:
        model = Review
        fields = [
            "rating",
            "food_quality_rating",
            "service_quality_rating",
            "ambience_rating",
            "location_rating",
            "value_rating",
            "dietary_accommodation_rating",
            "cleanliness_rating",
            "comment",
        ]
        labels = {
            "rating": "Overall rating",
            "food_quality_rating": "Food quality",
            "service_quality_rating": "Service quality",
            "ambience_rating": "Ambience",
            "location_rating": "Location & accessibility",
            "value_rating": "Price-to-value",
            "dietary_accommodation_rating": "Dietary accommodation",
            "cleanliness_rating": "Cleanliness",
            "comment": "Written review",
        }
        widgets = {
            "rating": forms.Select(
                choices=[(i, f"{i} Star{'s' if i > 1 else ''}") for i in range(1, 6)],
                attrs={"class": "form-control"},
            ),
            "food_quality_rating": forms.Select(
                choices=[(i, f"{i} / 5") for i in range(1, 6)],
                attrs={"class": "form-control"},
            ),
            "service_quality_rating": forms.Select(
                choices=[(i, f"{i} / 5") for i in range(1, 6)],
                attrs={"class": "form-control"},
            ),
            "ambience_rating": forms.Select(
                choices=[(i, f"{i} / 5") for i in range(1, 6)],
                attrs={"class": "form-control"},
            ),
            "location_rating": forms.Select(
                choices=[(i, f"{i} / 5") for i in range(1, 6)],
                attrs={"class": "form-control"},
            ),
            "value_rating": forms.Select(
                choices=[(i, f"{i} / 5") for i in range(1, 6)],
                attrs={"class": "form-control"},
            ),
            "dietary_accommodation_rating": forms.Select(
                choices=[(i, f"{i} / 5") for i in range(1, 6)],
                attrs={"class": "form-control"},
            ),
            "cleanliness_rating": forms.Select(
                choices=[(i, f"{i} / 5") for i in range(1, 6)],
                attrs={"class": "form-control"},
            ),
            "comment": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Write your review here...",
                }
            ),
        }


class ModerationReportForm(forms.ModelForm):
    """
    Form for users to report content or other users.
    """

    class Meta:
        model = ModerationReport
        fields = ["reason", "details"]
        widgets = {
            "reason": forms.Select(attrs={"class": "form-control"}),
            "details": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Provide more details about why you are reporting this...",
                }
            ),
        }


class ReviewResponseForm(forms.ModelForm):
    """
    Form for restaurant owners to post or edit a public response to a review.
    """

    class Meta:
        model = ReviewResponse
        fields = ["response_text"]
        labels = {
            "response_text": "Public response",
        }
        widgets = {
            "response_text": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Thank the customer, clarify concerns, or explain next steps.",
                }
            )
        }


class RestaurantCommunicationSettingsForm(forms.ModelForm):
    """
    Form for restaurant owners to manage their communication settings.
    Controls the messaging on/off toggle and available response hours.
    """

    response_hours_start = forms.TimeField(
        required=False,
        input_formats=[
            "%H:%M:%S",
            "%H:%M",
            "%H",
            "%I:%M %p",
            "%I:%M%p",
            "%I %p",
            "%I%p",
            "%I:%M %P",
            "%I:%M%P",
            "%I %P",
            "%I%P",
        ],
        label="Response Hours Start",
        help_text="Earliest time you typically respond to messages (optional).",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "e.g. 11:00 AM or 11pm",
            }
        ),
    )
    response_hours_end = forms.TimeField(
        required=False,
        input_formats=[
            "%H:%M:%S",
            "%H:%M",
            "%H",
            "%I:%M %p",
            "%I:%M%p",
            "%I %p",
            "%I%p",
            "%I:%M %P",
            "%I:%M%P",
            "%I %P",
            "%I%P",
        ],
        label="Response Hours End",
        help_text="Latest time you typically respond to messages (optional).",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "e.g. 4:00 PM or 4pm",
            }
        ),
    )

    class Meta:
        model = Restaurant
        fields = [
            "messaging_enabled",
            "response_hours_start",
            "response_hours_end",
        ]
        labels = {
            "messaging_enabled": "Enable Messaging",
        }
        help_texts = {
            "messaging_enabled": "When disabled, diners will not be able to send you new messages.",
        }
        widgets = {
            "messaging_enabled": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Format initial time values as 12-hour AM/PM strings for display
        if self.instance:
            if self.instance.response_hours_start:
                self.initial["response_hours_start"] = (
                    self.instance.response_hours_start.strftime("%I:%M %p")
                )
            if self.instance.response_hours_end:
                self.initial["response_hours_end"] = (
                    self.instance.response_hours_end.strftime("%I:%M %p")
                )

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("response_hours_start")
        end = cleaned_data.get("response_hours_end")
        if start and end and start >= end:
            raise forms.ValidationError(
                "Response hours start time must be before end time."
            )
        return cleaned_data
