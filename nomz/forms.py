from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import UserProfile, Restaurant, RestaurantPhoto


class UserRegisterForm(UserCreationForm):
    """
    Custom user registration form that extends Django's UserCreationForm.
    Adds email field and improves styling.
    """
    # Add the Role selection field
    ROLE_CHOICES = [
        ('diner', 'I am a Diner'),
        ('restaurant', 'I am a Restaurant Owner'),
    ]
    role = forms.ChoiceField(
        choices=ROLE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}) 
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Email address'
        })
    )
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Username'
        })
    )
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Password'
        })
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm password'
        })
    )

    class Meta:
        model = User
        fields = ['email', 'username', 'role', 'password1', 'password2']

    def clean_email(self):
        """Ensure email is unique"""
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('This email is already registered.')
        return email

    def save(self, commit=True):
        """Save user with email AND create their UserProfile"""
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
            # This is where the backend permanently stores the role!
            UserProfile.objects.create(
                user=user,
                role=self.cleaned_data['role']
            )
        return user


class UserLoginForm(AuthenticationForm):
    """
    Custom login form that extends Django's AuthenticationForm.
    Adds Bootstrap styling for better UI.
    """
    username = forms.CharField(
        max_length=254,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Username or Email'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Password'
        })
    )


class RestaurantProfileForm(forms.ModelForm):
    """
    Form for restaurant owners to create and edit their restaurant profile.
    Handles description, hours, cuisine type, and price range.
    """
    class Meta:
        model = Restaurant
        fields = ['name', 'description', 'cuisine_type', 'price_range', 
                  'hours_open', 'hours_close', 'address', 'phone', 'website', 'email']
        labels = {
            'name': 'Restaurant Name',
            'description': 'Description & Ambiance',
            'cuisine_type': 'Cuisine Type',
            'price_range': 'Price Range',
            'hours_open': 'Opening Time',
            'hours_close': 'Closing Time',
            'address': 'Address',
            'phone': 'Phone Number',
            'website': 'Website',
            'email': 'Contact Email',
        }
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., "The Italian Corner"'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Describe your restaurant, cuisine style, and special offerings...'
            }),
            'cuisine_type': forms.Select(attrs={'class': 'form-control'}),
            'price_range': forms.Select(attrs={'class': 'form-control'}),
            'hours_open': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time'
            }),
            'hours_close': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time'
            }),
            'address': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., "123 Main St, New York, NY 10001"'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '(123) 456-7890'
            }),
            'website': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://www.example.com'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'contact@restaurant.com'
            }),
        }


class RestaurantAvailabilityForm(forms.ModelForm):
    """
    Form for restaurant owners to mark temporary unavailability.
    """
    class Meta:
        model = Restaurant
        fields = ['is_temporarily_unavailable', 'unavailable_reason', 'unavailable_until']
        labels = {
            'is_temporarily_unavailable': 'Mark as Temporarily Unavailable',
            'unavailable_reason': 'Reason for Unavailability',
            'unavailable_until': 'Available Again On',
        }
        widgets = {
            'is_temporarily_unavailable': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'unavailable_reason': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'e.g., Renovations, Special Event, Staffing Issues...'
            }),
            'unavailable_until': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
        }


class RestaurantActivationForm(forms.ModelForm):
    """
    Form for restaurant owners to activate/deactivate their profile.
    """
    class Meta:
        model = Restaurant
        fields = ['is_active']
        labels = {
            'is_active': 'Profile Active & Visible to Customers',
        }
        widgets = {
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }


class RestaurantPhotoForm(forms.ModelForm):
    """
    Form for uploading restaurant photos.
    """
    class Meta:
        model = RestaurantPhoto
        fields = ['photo', 'caption', 'is_primary']
        labels = {
            'photo': 'Photo',
            'caption': 'Photo Caption',
            'is_primary': 'Set as Main Photo',
        }
        widgets = {
            'photo': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'caption': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., "Dining Area", "Signature Dish"'
            }),
            'is_primary': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }

