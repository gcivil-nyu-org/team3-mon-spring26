#!/bin/bash

# Quick Local Testing Setup Script
# This script automates the setup and testing process

set -e  # Exit on any error

echo "🚀 Starting Restaurant Profile Management Local Testing Setup..."
echo ""

# Step 1: Activate virtual environment
echo "📦 Activating virtual environment..."
source .venv/bin/activate

# Step 2: Run migrations
echo "🗄️  Running database migrations..."
python manage.py migrate --no-input

# Step 3: Create test users
echo "👤 Creating test users..."
python manage.py shell << END
from django.contrib.auth.models import User
from nomz.models import UserProfile

# Check if users already exist
if not User.objects.filter(username='restaurant_owner').exists():
    # Create restaurant owner
    restaurant_owner = User.objects.create_user(
        username='restaurant_owner',
        email='owner@restaurant.com',
        password='testpass123'
    )
    UserProfile.objects.create(user=restaurant_owner, role='restaurant')
    print("✅ Restaurant owner created: restaurant_owner / testpass123")
else:
    print("⏭️  Restaurant owner already exists")

# Create diner
if not User.objects.filter(username='diner_user').exists():
    diner = User.objects.create_user(
        username='diner_user',
        email='diner@test.com',
        password='testpass123'
    )
    UserProfile.objects.create(user=diner, role='diner')
    print("✅ Diner user created: diner_user / testpass123")
else:
    print("⏭️  Diner user already exists")

# Create admin
if not User.objects.filter(username='admin').exists():
    admin = User.objects.create_superuser(
        username='admin',
        email='admin@test.com',
        password='adminpass123'
    )
    print("✅ Admin user created: admin / adminpass123")
else:
    print("⏭️  Admin user already exists")
END

echo ""
echo "✅ Setup complete!"
echo ""
echo "📋 Test Credentials:"
echo "   Restaurant Owner: restaurant_owner / testpass123"
echo "   Diner User: diner_user / testpass123"
echo "   Admin: admin / adminpass123"
echo ""

# Step 4: Offer to run tests
read -p "Do you want to run tests now? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🧪 Running tests..."
    python manage.py test nomz --verbosity=2
    echo ""
    echo "✅ Tests completed!"
fi

# Step 5: Offer to start server
read -p "Do you want to start the development server? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "🌐 Starting development server..."
    echo "📱 Open browser and go to: http://localhost:8000"
    echo "🧑‍💻 Admin panel: http://localhost:8000/admin/"
    echo ""
    echo "Press Ctrl+C to stop the server"
    echo ""
    python manage.py runserver
fi

echo ""
echo "✨ Testing session complete!"
