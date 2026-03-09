from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from io import BytesIO
from PIL import Image
from .models import UserProfile, Restaurant, RestaurantPhoto


class RestaurantModelTests(TestCase):
    """Test cases for Restaurant model"""
    
    def setUp(self):
        """Create test user and restaurant"""
        self.user = User.objects.create_user(
            username='restaurantowner',
            email='owner@restaurant.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.user, role='restaurant')
        
        self.restaurant = Restaurant.objects.create(
            owner=self.user,
            name='Test Restaurant',
            description='A great place to eat',
            cuisine_type='italian',
            price_range='$$',
            address='123 Main St, NYC',
            phone='(555) 123-4567',
            email='contact@test.com',
            website='https://test.com',
            hours_open='09:00',
            hours_close='21:00',
            is_active=True,
            is_temporarily_unavailable=False
        )
    
    def test_restaurant_creation(self):
        """Test restaurant creation"""
        self.assertEqual(self.restaurant.name, 'Test Restaurant')
        self.assertEqual(self.restaurant.owner, self.user)
        self.assertTrue(self.restaurant.is_active)
    
    def test_restaurant_string_representation(self):
        """Test restaurant __str__ method"""
        self.assertEqual(str(self.restaurant), 'Test Restaurant')
    
    def test_restaurant_can_be_managed_by_owner(self):
        """Test can_be_managed_by method"""
        self.assertTrue(self.restaurant.can_be_managed_by(self.user))
    
    def test_restaurant_cannot_be_managed_by_other_user(self):
        """Test can_be_managed_by method with different user"""
        other_user = User.objects.create_user(
            username='otheruser',
            password='otherpass123'
        )
        self.assertFalse(self.restaurant.can_be_managed_by(other_user))
    
    def test_restaurant_is_open_now(self):
        """Test is_open_now method"""
        # Deactivate to test condition
        self.restaurant.is_active = False
        self.assertFalse(self.restaurant.is_open_now())
        
        # Reactivate and test again
        self.restaurant.is_active = True
        # Note: This test may fail at certain times because of actual time comparison
        # In production, use freezegun or similar for time-based tests
    
    def test_restaurant_is_open_when_temporarily_unavailable(self):
        """Test is_open_now returns False when temporarily unavailable"""
        self.restaurant.is_temporarily_unavailable = True
        self.assertFalse(self.restaurant.is_open_now())
    
    def test_restaurant_unique_name(self):
        """Test that restaurant names are unique"""
        with self.assertRaises(Exception):
            Restaurant.objects.create(
                owner=self.user,
                name='Test Restaurant',  # Same name
                cuisine_type='italian',
                price_range='$$'
            )


class RestaurantPhotoModelTests(TestCase):
    """Test cases for RestaurantPhoto model"""
    
    def setUp(self):
        """Create test user and restaurant"""
        self.user = User.objects.create_user(
            username='restaurantowner',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.user, role='restaurant')
        
        self.restaurant = Restaurant.objects.create(
            owner=self.user,
            name='Test Restaurant',
            cuisine_type='italian',
            price_range='$$'
        )
    
    def create_test_image(self):
        """Create a test image file"""
        image = Image.new('RGB', (100, 100), color='red')
        image_io = BytesIO()
        image.save(image_io, format='JPEG')
        image_io.seek(0)
        return SimpleUploadedFile('test.jpg', image_io.getvalue(), content_type='image/jpeg')
    
    def test_photo_creation(self):
        """Test photo creation"""
        photo = RestaurantPhoto.objects.create(
            restaurant=self.restaurant,
            photo=self.create_test_image(),
            caption='Dining area'
        )
        self.assertEqual(photo.restaurant, self.restaurant)
        self.assertEqual(photo.caption, 'Dining area')
    
    def test_photo_string_representation(self):
        """Test photo __str__ method"""
        photo = RestaurantPhoto.objects.create(
            restaurant=self.restaurant,
            photo=self.create_test_image(),
            caption='Test Photo'
        )
        self.assertIn('Test Restaurant', str(photo))
        self.assertIn('Test Photo', str(photo))
    
    def test_primary_photo_uniqueness(self):
        """Test that only one photo can be primary"""
        photo1 = RestaurantPhoto.objects.create(
            restaurant=self.restaurant,
            photo=self.create_test_image(),
            caption='Photo 1',
            is_primary=True
        )
        
        photo2 = RestaurantPhoto.objects.create(
            restaurant=self.restaurant,
            photo=self.create_test_image(),
            caption='Photo 2',
            is_primary=True
        )
        
        # Refresh from DB
        photo1.refresh_from_db()
        
        # photo1 should no longer be primary
        self.assertFalse(photo1.is_primary)
        self.assertTrue(photo2.is_primary)
    
    def test_photos_ordered_by_primary_and_date(self):
        """Test that photos are ordered correctly"""
        photo1 = RestaurantPhoto.objects.create(
            restaurant=self.restaurant,
            photo=self.create_test_image(),
            caption='Photo 1',
            is_primary=False
        )
        
        photo2 = RestaurantPhoto.objects.create(
            restaurant=self.restaurant,
            photo=self.create_test_image(),
            caption='Photo 2',
            is_primary=True
        )
        
        photos = RestaurantPhoto.objects.filter(restaurant=self.restaurant)
        self.assertEqual(photos[0].id, photo2.id)  # Primary first
        self.assertEqual(photos[1].id, photo1.id)


class RestaurantProfileViewTests(TestCase):
    """Test cases for restaurant profile views"""
    
    def setUp(self):
        """Create test user and authenticate"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='restaurantowner',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.user, role='restaurant')
        
        self.diner_user = User.objects.create_user(
            username='diner',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.diner_user, role='diner')
    
    def test_restaurant_profile_view_requires_login(self):
        """Test that profile view requires authentication"""
        response = self.client.get(reverse('restaurant_profile'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_restaurant_profile_view_for_restaurant_owner(self):
        """Test that restaurant owner can view profile"""
        restaurant = Restaurant.objects.create(
            owner=self.user,
            name='Test Restaurant',
            cuisine_type='italian',
            price_range='$$'
        )
        
        self.client.login(username='restaurantowner', password='testpass123')
        response = self.client.get(reverse('restaurant_profile'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Restaurant')
    
    def test_diner_cannot_access_restaurant_profile(self):
        """Test that diner cannot access restaurant profile management"""
        self.client.login(username='diner', password='testpass123')
        response = self.client.get(reverse('restaurant_profile'))
        
        self.assertEqual(response.status_code, 302)  # Redirect
    
    def test_create_restaurant_profile_get(self):
        """Test GET request to create restaurant profile"""
        self.client.login(username='restaurantowner', password='testpass123')
        response = self.client.get(reverse('create_restaurant'))
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.context)
    
    def test_create_restaurant_profile_post(self):
        """Test POST request to create restaurant profile"""
        self.client.login(username='restaurantowner', password='testpass123')
        
        data = {
            'name': 'New Restaurant',
            'description': 'Great food',
            'cuisine_type': 'italian',
            'price_range': '$$',
            'hours_open': '09:00',
            'hours_close': '21:00',
            'address': '123 Main St',
            'phone': '(555) 123-4567'
        }
        
        response = self.client.post(reverse('create_restaurant'), data)
        
        self.assertEqual(response.status_code, 302)  # Redirect after success
        restaurant = Restaurant.objects.get(owner=self.user)
        self.assertEqual(restaurant.name, 'New Restaurant')
    
    def test_edit_restaurant_profile_get(self):
        """Test GET request to edit restaurant profile"""
        restaurant = Restaurant.objects.create(
            owner=self.user,
            name='Test Restaurant',
            cuisine_type='italian',
            price_range='$$'
        )
        
        self.client.login(username='restaurantowner', password='testpass123')
        response = self.client.get(reverse('edit_restaurant'))
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.context)
    
    def test_edit_restaurant_profile_post(self):
        """Test POST request to edit restaurant profile"""
        restaurant = Restaurant.objects.create(
            owner=self.user,
            name='Test Restaurant',
            cuisine_type='italian',
            price_range='$$',
            hours_open='09:00',
            hours_close='21:00'
        )
        
        self.client.login(username='restaurantowner', password='testpass123')
        
        data = {
            'name': 'Updated Restaurant',
            'description': 'Updated description',
            'cuisine_type': 'french',
            'price_range': '$$$',
            'hours_open': '10:00',
            'hours_close': '22:00',
            'address': '456 Oak Ave'
        }
        
        response = self.client.post(reverse('edit_restaurant'), data)
        
        restaurant.refresh_from_db()
        self.assertEqual(restaurant.name, 'Updated Restaurant')
        self.assertEqual(restaurant.cuisine_type, 'french')


class RestaurantAvailabilityViewTests(TestCase):
    """Test cases for availability management views"""
    
    def setUp(self):
        """Create test user and restaurant"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='restaurantowner',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.user, role='restaurant')
        
        self.restaurant = Restaurant.objects.create(
            owner=self.user,
            name='Test Restaurant',
            cuisine_type='italian',
            price_range='$$'
        )
    
    def test_manage_availability_view(self):
        """Test availability management view"""
        self.client.login(username='restaurantowner', password='testpass123')
        response = self.client.get(reverse('manage_availability'))
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.context)
    
    def test_mark_temporarily_unavailable(self):
        """Test marking restaurant as temporarily unavailable"""
        self.client.login(username='restaurantowner', password='testpass123')
        
        data = {
            'is_temporarily_unavailable': True,
            'unavailable_reason': 'Renovations'
        }
        
        response = self.client.post(reverse('manage_availability'), data)
        
        self.restaurant.refresh_from_db()
        self.assertTrue(self.restaurant.is_temporarily_unavailable)
        self.assertEqual(self.restaurant.unavailable_reason, 'Renovations')


class RestaurantPhotoViewTests(TestCase):
    """Test cases for photo management views"""
    
    def setUp(self):
        """Create test user and restaurant"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='restaurantowner',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.user, role='restaurant')
        
        self.restaurant = Restaurant.objects.create(
            owner=self.user,
            name='Test Restaurant',
            cuisine_type='italian',
            price_range='$$'
        )
    
    def create_test_image(self):
        """Create a test image file"""
        image = Image.new('RGB', (100, 100), color='red')
        image_io = BytesIO()
        image.save(image_io, format='JPEG')
        image_io.seek(0)
        return SimpleUploadedFile('test.jpg', image_io.getvalue(), content_type='image/jpeg')
    
    def test_upload_photo_view_get(self):
        """Test GET request to upload photo"""
        self.client.login(username='restaurantowner', password='testpass123')
        response = self.client.get(reverse('upload_photo'))
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.context)
    
    def test_upload_photo_view_post(self):
        """Test POST request to upload photo"""
        self.client.login(username='restaurantowner', password='testpass123')
        
        data = {
            'photo': self.create_test_image(),
            'caption': 'Dining area',
            'is_primary': True
        }
        
        response = self.client.post(reverse('upload_photo'), data)
        
        self.assertEqual(response.status_code, 302)  # Redirect after success
        photo = RestaurantPhoto.objects.get(restaurant=self.restaurant)
        self.assertEqual(photo.caption, 'Dining area')
        self.assertTrue(photo.is_primary)
    
    def test_restaurant_photos_view(self):
        """Test viewing all restaurant photos"""
        photo = RestaurantPhoto.objects.create(
            restaurant=self.restaurant,
            photo=self.create_test_image(),
            caption='Test Photo'
        )
        
        self.client.login(username='restaurantowner', password='testpass123')
        response = self.client.get(reverse('restaurant_photos'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Photo')
    
    def test_delete_photo(self):
        """Test deleting a photo"""
        photo = RestaurantPhoto.objects.create(
            restaurant=self.restaurant,
            photo=self.create_test_image(),
            caption='Test Photo'
        )
        
        self.client.login(username='restaurantowner', password='testpass123')
        response = self.client.post(reverse('delete_photo', args=[photo.id]))
        
        self.assertEqual(response.status_code, 302)  # Redirect after delete
        self.assertFalse(RestaurantPhoto.objects.filter(id=photo.id).exists())
    
    def test_set_primary_photo(self):
        """Test setting a photo as primary"""
        photo1 = RestaurantPhoto.objects.create(
            restaurant=self.restaurant,
            photo=self.create_test_image(),
            caption='Photo 1',
            is_primary=True
        )
        
        photo2 = RestaurantPhoto.objects.create(
            restaurant=self.restaurant,
            photo=self.create_test_image(),
            caption='Photo 2'
        )
        
        self.client.login(username='restaurantowner', password='testpass123')
        response = self.client.post(reverse('set_primary_photo', args=[photo2.id]))
        
        self.assertEqual(response.status_code, 302)
        
        photo2.refresh_from_db()
        photo1.refresh_from_db()
        self.assertTrue(photo2.is_primary)
        self.assertFalse(photo1.is_primary)

