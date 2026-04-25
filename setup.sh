#!/bin/bash

# Local Development Setup Script for Nomz Project
# This script helps set up your local environment for development

echo "🚀 Setting up Nomz Project for Local Development..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "📝 Creating .env file from .env.example..."
    cp .env.example .env
    echo "✅ .env file created. Update it with your local settings."
else
    echo "✅ .env file already exists"
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "🐍 Creating Python virtual environment..."
    python -m venv venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source venv/bin/activate

# Install requirements
echo "📦 Installing Python dependencies..."
pip install -r requirements-dev.txt

# Run migrations
echo "🗄️  Running database migrations..."
python manage.py migrate

# Collect static files (for development)
echo "📁 Collecting static files..."
python manage.py collectstatic --noinput

echo ""
echo "✅ Setup complete! You're ready to start developing."
echo ""
echo "To run the development server:"
echo "  python manage.py runserver"
echo ""
echo "To run tests:"
echo "  python manage.py test"
echo ""
echo "To deactivate virtual environment:"
echo "  deactivate"
echo ""
