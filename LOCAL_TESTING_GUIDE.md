# Local Testing Guide - Restaurant Profile Management

## Prerequisites ✅

Make sure you have:
- Python virtual environment activated
- All dependencies installed from `requirements.txt`
- `.env` file configured for development (already set up)

---

## Step 1: Set Up the Database

### Reset Database (Start Fresh)
```bash
# Delete old database
rm db.sqlite3

# Create fresh database with migrations
python manage.py migrate
```

### Or Keep Existing Database
```bash
# Just apply migrations
python manage.py migrate
```

---

## Step 2: Create Test Users

Run this command to create test users for local testing:

```bash
python manage.py shell
```

Then paste this code:

```python
from django.contrib.auth.models import User
from nomz.models import UserProfile

# Create a restaurant owner
restaurant_owner = User.objects.create_user(
    username='restaurant_owner',
    email='owner@restaurant.com',
    password='testpass123'
)
UserProfile.objects.create(user=restaurant_owner, role='restaurant')

# Create a diner user
diner = User.objects.create_user(
    username='diner_user',
    email='diner@test.com',
    password='testpass123'
)
UserProfile.objects.create(user=diner, role='diner')

# Create admin user
admin = User.objects.create_superuser(
    username='admin',
    email='admin@test.com',
    password='adminpass123'
)

print("✅ Test users created successfully!")
print("\nTest Credentials:")
print("Restaurant Owner: restaurant_owner / testpass123")
print("Diner: diner_user / testpass123")
print("Admin: admin / adminpass123")
```

Exit the shell with `exit()` or `Ctrl+D`

---

## Step 3: Start the Development Server

```bash
python manage.py runserver
```

You should see:
```
Starting development server at http://127.0.0.1:8000/
```

---

## Step 4: Test Restaurant Profile Management

### 4.1 Login as Restaurant Owner

1. Go to `http://localhost:8000/login/`
2. Enter credentials:
   - **Username**: `restaurant_owner`
   - **Password**: `testpass123`
3. Click Login

### 4.2 Create Restaurant Profile

1. Click "View Profile" or go to `/restaurant/profile/`
2. You should see "You haven't created a restaurant profile yet"
3. Click "Create Restaurant Profile"
4. Fill in the form:
   ```
   Restaurant Name: The Italian Corner
   Description: Authentic Italian cuisine with a warm atmosphere
   Cuisine Type: Italian
   Price Range: $$
   Hours Open: 11:00
   Hours Close: 22:00
   Address: 123 Main St, New York, NY
   Phone: (555) 123-4567
   Website: https://example.com
   Email: contact@italian.com
   ```
5. Click "Create Profile"

**Expected Result**: Profile created and redirected to `restaurant_profile` page ✅

### 4.3 Edit Restaurant Profile

1. Go to Restaurant Profile (should be displayed)
2. Click "Edit Profile"
3. Make changes (e.g., change cuisine to French)
4. Click "Save Changes"

**Expected Result**: Profile updated successfully ✅

### 4.4 Upload Restaurant Photos

1. On Restaurant Profile, click "Manage Photos"
2. Click "Upload New Photo"
3. Select an image file (can use any image)
4. Add Caption: "Dining Area"
5. Check "Set as Main Photo"
6. Click "Upload Photo"

**Expected Result**: Photo uploaded and displayed in gallery ✅

### 4.5 Upload More Photos and Test Primary

1. Upload 2-3 more photos with different captions
2. Go back to "Manage Photos"
3. Click "Set as Main" on a different photo
4. Verify the previous primary photo is no longer marked as main

**Expected Result**: Only one photo marked as "Main" at a time ✅

### 4.6 Delete a Photo

1. In "Manage Photos" view
2. Click "Delete" on a photo
3. Confirm deletion

**Expected Result**: Photo removed from gallery ✅

### 4.7 Mark Restaurant Temporarily Unavailable

1. Go to Restaurant Profile
2. Click "Manage Availability"
3. Check "Mark as Temporarily Unavailable"
4. Add reason: "Renovations in progress"
5. Set "Available Again On": (pick a date in the future)
6. Click "Update Availability"

**Expected Result**: Status changes to "Temporarily Unavailable" ✅

### 4.8 Deactivate Profile

1. Go to Restaurant Profile
2. Click "Profile Status"
3. Uncheck "Profile Active & Visible to Customers"
4. Click "Deactivate Profile"

**Expected Result**: Profile marked as inactive with warning message ✅

### 4.9 Reactivate Profile

1. Still on activation page
2. Check "Profile Active & Visible to Customers"
3. Click "Activate Profile"

**Expected Result**: Profile is active again ✅

---

## Step 5: Test Permissions

### Test Diner Cannot Access Restaurant Features

1. Logout from restaurant owner account
2. Login as diner:
   - **Username**: `diner_user`
   - **Password**: `testpass123`
3. Try to access `/restaurant/profile/`

**Expected Result**: Redirected with error message "You do not have permission" ✅

### Test User Can Only Manage Their Own Restaurant

1. Create second restaurant owner in admin
2. Login as first restaurant owner
3. Try to access second owner's restaurant programmatically

**Expected Result**: Permission denied ✅

---

## Step 6: Run Automated Tests

```bash
# Run all tests
python manage.py test nomz

# Run with verbose output
python manage.py test nomz --verbosity=2

# Run specific test class
python manage.py test nomz.tests.RestaurantProfileViewTests

# Run specific test method
python manage.py test nomz.tests.RestaurantProfileViewTests.test_create_restaurant_profile_post

# Run with coverage (if installed)
coverage run --source='nomz' manage.py test
coverage report
coverage html
```

**Expected Result**: All 25 tests passing ✅

---

## Step 7: Test Form Validation

### Test Invalid Form Submission

1. Go to "Create Restaurant Profile"
2. Leave "Restaurant Name" blank
3. Click "Create Profile"

**Expected Result**: Form shows error "This field is required" ✅

### Test Duplicate Restaurant Name

1. Create a restaurant with name "Test Restaurant"
2. Try to create another with same name
3. Should show unique constraint error

**Expected Result**: Error message displayed ✅

### Test Invalid Email Format

1. Go to "Edit Profile"
2. Enter invalid email: `notanemail`
3. Click "Save Changes"

**Expected Result**: Form validation error ✅

### Test Invalid URL Format

1. Go to "Edit Profile"
2. Enter phone: `(555) 123-4567` (valid)
3. Enter website: `notaurl` (invalid)
4. Click "Save Changes"

**Expected Result**: Website validation error ✅

---

## Step 8: Test Admin Interface

### Add Restaurant Model to Admin

The models should already be registered. Check:

1. Go to `http://localhost:8000/admin/`
2. Login with admin credentials:
   - **Username**: `admin`
   - **Password**: `adminpass123`

3. You should see:
   - Restaurants
   - Restaurant Photos

4. Click "Restaurants" to see all restaurants

**Expected Result**: Admin interface displays all restaurants ✅

---

## Step 9: Test Photo Upload with Different File Types

### Upload Different Image Formats

1. Go to "Upload Photo"
2. Test each format:
   - `.jpg` - Should work ✅
   - `.png` - Should work ✅
   - `.gif` - Should work ✅
   - `.webp` - Should work ✅

### Test Invalid File Type

1. Go to "Upload Photo"
2. Try uploading a `.txt` or `.pdf` file

**Expected Result**: Form shows error "upload a valid image" ✅

### Test File Size

1. Create a large image (> 5MB if limit is set)
2. Try uploading

**Expected Result**: Appropriate error message ✅

---

## Step 10: Check Database State

```bash
python manage.py shell
```

```python
from nomz.models import Restaurant, RestaurantPhoto

# View all restaurants
restaurants = Restaurant.objects.all()
for r in restaurants:
    print(f"Restaurant: {r.name}")
    print(f"  Owner: {r.owner.username}")
    print(f"  Active: {r.is_active}")
    print(f"  Temporarily Unavailable: {r.is_temporarily_unavailable}")
    print(f"  Photos: {r.photos.count()}")
    print()

# View all photos
photos = RestaurantPhoto.objects.all()
for p in photos:
    print(f"Photo: {p.caption}")
    print(f"  Restaurant: {p.restaurant.name}")
    print(f"  Primary: {p.is_primary}")
    print()
```

---

## Step 11: Test User Flow - Complete Workflow

### Scenario: New Restaurant Owner

1. **Register** as new user
   - Go to `/register/`
   - Create account, select "I am a Restaurant Owner"

2. **Create Profile**
   - Go to dashboard
   - Click "View Profile"
   - Create restaurant details

3. **Upload Photos**
   - Upload 3-5 photos
   - Set main photo
   - View gallery

4. **Manage Availability**
   - Mark as temporarily unavailable (e.g., for renovations)
   - Set return date

5. **View Profile**
   - Check all information is displayed correctly
   - Verify status badges show correct status

6. **Deactivate/Reactivate**
   - Deactivate profile
   - Verify profile is invisible
   - Reactivate
   - Verify profile is visible again

**Expected Result**: Complete workflow works smoothly ✅

---

## Step 12: Performance Testing (Optional)

### Test with Multiple Photos

1. Upload 20+ photos to one restaurant
2. View photo management page
3. Check loading speed

**Expected Result**: Page loads quickly, pagination works if implemented ✅

### Test Multiple Restaurants

1. Create 3-5 test restaurants
2. Upload photos to each
3. Verify access control still works

**Expected Result**: No data mixing between restaurants ✅

---

## Common Issues & Troubleshooting

### Issue: "No such table: nomz_restaurant"
**Solution**: Run migrations
```bash
python manage.py migrate
```

### Issue: Images not displaying
**Solution**: Ensure media files are served
```bash
python manage.py collectstatic --noinput
```

### Issue: Permission denied errors
**Solution**: Check user has restaurant role
```python
from nomz.models import UserProfile
user = User.objects.get(username='restaurant_owner')
print(user.userprofile.role)  # Should be 'restaurant'
```

### Issue: Photos not uploading
**Solution**: Check media directory permissions
```bash
mkdir -p media/restaurant_photos/
chmod 755 media/restaurant_photos/
```

### Issue: Form validation failing
**Solution**: Check form error details
```python
# In shell or template, print form.errors
```

---

## Checklist ✅

- [ ] Database set up and migrated
- [ ] Test users created
- [ ] Development server running
- [ ] Can login as restaurant owner
- [ ] Can create restaurant profile
- [ ] Can edit all restaurant fields
- [ ] Can upload photos
- [ ] Can set primary photo
- [ ] Can delete photos
- [ ] Can mark temporarily unavailable
- [ ] Can deactivate/reactivate profile
- [ ] Diner cannot access restaurant features
- [ ] All 25 tests passing
- [ ] Form validation working
- [ ] Admin interface accessible
- [ ] Complete user workflow successful

---

## Next: Push to Develop

Once all tests pass locally:

```bash
# Switch to develop branch
git checkout develop

# Merge your changes
git merge ananya

# Push to develop
git push origin develop

# GitHub Actions will automatically run tests
```

Monitor the GitHub Actions workflow to ensure CI/CD passes.

---

## Commands Quick Reference

```bash
# Activate venv
source .venv/bin/activate

# Run server
python manage.py runserver

# Run tests
python manage.py test nomz --verbosity=2

# Create superuser
python manage.py createsuperuser

# Database shell
python manage.py shell

# Make migrations
python manage.py makemigrations

# Run migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput
```

Happy testing! 🚀
