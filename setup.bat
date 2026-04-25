@echo off
REM Local Development Setup Script for Nomz Project (Windows)
REM This script helps set up your local environment for development

echo.
echo 🚀 Setting up Nomz Project for Local Development...
echo.

REM Check if .env exists
if not exist .env (
    echo 📝 Creating .env file from .env.example...
    copy .env.example .env
    echo ✅ .env file created. Update it with your local settings.
) else (
    echo ✅ .env file already exists
)

REM Create virtual environment if it doesn't exist
if not exist venv (
    echo 🐍 Creating Python virtual environment...
    python -m venv venv
    echo ✅ Virtual environment created
) else (
    echo ✅ Virtual environment already exists
)

REM Activate virtual environment
echo 🔌 Activating virtual environment...
call venv\Scripts\activate.bat

REM Install requirements
echo 📦 Installing Python dependencies...
pip install -r requirements-dev.txt

REM Run migrations
echo 🗄️  Running database migrations...
python manage.py migrate

REM Collect static files (for development)
echo 📁 Collecting static files...
python manage.py collectstatic --noinput

echo.
echo ✅ Setup complete! You're ready to start developing.
echo.
echo To run the development server:
echo   python manage.py runserver
echo.
echo To run tests:
echo   python manage.py test
echo.
echo To deactivate virtual environment:
echo   deactivate
echo.
