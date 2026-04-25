# Nomz — NYC Restaurant Discovery Platform

[![Build Status](https://app.travis-ci.com/gcivil-nyu-org/team3-mon-spring26.svg?branch=develop)](https://app.travis-ci.com/gcivil-nyu-org/team3-mon-spring26)
[![Coverage Status](https://coveralls.io/repos/github/gcivil-nyu-org/team3-mon-spring26/badge.svg?branch=production)](https://coveralls.io/github/gcivil-nyu-org/team3-mon-spring26?branch=production)

Nomz is a full-stack web application for discovering, reviewing, and managing NYC restaurants. It combines real-time NYC Open Data ingestion, a multi-factor composite scoring system, personalized recommendations, and social features like friend chat and shared restaurant lists.

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Local Development Setup](#local-development-setup)
- [Environment Variables](#environment-variables)
- [Running Tests](#running-tests)
- [CI/CD Pipeline](#cicd-pipeline)
- [Deployment](#deployment)
- [API Endpoints](#api-endpoints)

---

## Features

- **NYC Open Data Ingestion** — Pulls from three NYC feeds (Directory of Eateries, Dining Out NYC, DOHMH Inspections), deduplicates, normalizes, and matches records to restaurant profiles.
- **Composite Scoring** — Multi-factor restaurant score based on inspection grades, review ratings, price value, and operational status, with full audit history and anomaly detection.
- **Personalized Recommendations** — Preference-based scoring with learnable weights (cuisine, dietary needs, price, neighborhood, quality). Tracks user interactions and adjusts over time.
- **Multi-Dimensional Reviews** — Eight rating categories (overall, food, service, ambience, location, value, dietary accommodation, cleanliness) with restaurant owner responses.
- **Restaurant Ownership Claims** — Users can claim ingested restaurants with proof; admins approve or reject.
- **Diner ↔ Restaurant Messaging** — Direct conversations with unread notifications and configurable response hours.
- **Friend & Group Chat** — Friend-to-friend and group conversations with in-chat restaurant recommendations and a shared "Together List."
- **Content Moderation** — User-filed reports (spam, fraud, harassment) with an admin review queue.
- **Two-Factor Authentication** — TOTP-based 2FA via django-otp.
- **Admin Dashboard** — Pending approvals, user management, login logs with suspicious activity detection, moderation queue, score recalculation, system performance monitoring, and alerts.
- **Interactive Map** — Leaflet-based restaurant map with filtering and sorting.
- **AWS S3 Media Storage** — Optional S3 backend for static files and restaurant photos.

---

## Tech Stack

| Layer | Technologies |
|---|---|
| **Backend** | Python 3.12, Django 5.1+, Django REST Framework, Gunicorn |
| **Frontend** | Django Templates, Bootstrap 5, WhiteNoise |
| **Database** | SQLite (dev), PostgreSQL (prod via AWS RDS) |
| **Auth** | Django sessions, django-otp, django-two-factor-auth |
| **Storage** | WhiteNoise (static), AWS S3 + boto3 (optional) |
| **CI/CD** | Travis CI, Coveralls |
| **Hosting** | AWS Elastic Beanstalk |

---

## Project Structure

```
├── templates/               # Django templates (HTML, Bootstrap 5)
│   ├── base.html            # Base template with Bootstrap 5
│   ├── auth/                # Authentication templates
│   ├── nomz/                # Main app templates
│   └── admin/               # Admin interface templates
├── nomz/                    # Main Django app
│   ├── models.py            # 29 models (User, Restaurant, Review, Chat, etc.)
│   ├── spa_api.py           # JSON API endpoints for the web interface
│   ├── api_views.py         # Additional API views (map, messaging, claims)
│   ├── views.py             # Django view functions
│   ├── scoring.py           # Composite scoring algorithm
│   ├── filtering.py         # Restaurant filtering logic
│   ├── restaurant_sorting.py# Sorting and recommendation engine
│   ├── signals.py           # Django signals
│   ├── urls.py              # URL routing for HTML pages and JSON APIs
│   ├── ingestion/           # NYC Open Data ingestion pipeline
│   │   ├── runner.py        # Pipeline orchestrator
│   │   ├── sources/         # Per-feed data sources
│   │   └── utils/           # Parsing and normalization helpers
│   ├── migrations/          # Database migrations
│   └── management/commands/ # Custom Django management commands
├── restaurants/             # Django project config
│   ├── settings.py          # All settings (env-driven)
│   ├── urls.py              # Root URL config
│   └── wsgi.py
├── templates/               # Django templates (legacy, mostly redirects)
├── scripts/                 # Utility scripts (create_db.py)
├── data/                    # Fixture data
├── .ebextensions/           # Elastic Beanstalk config
├── .travis.yml              # CI/CD pipeline
├── Procfile                 # Gunicorn process definition
├── requirements.txt         # Python dependencies
└── manage.py
```

---

## Local Development Setup

### Prerequisites

- Python 3.12+
- Git

### 1. Clone the Repository

```bash
git clone https://github.com/gcivil-nyu-org/team3-mon-spring26.git
cd team3-mon-spring26
```

### 2. Set Up the Python Backend

```bash
# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate   # macOS/Linux
# .venv\Scripts\activate    # Windows

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment

Create a `.env` file in the project root (or rely on defaults for development):

```env
DEBUG=True
SECRET_KEY=your-dev-secret-key
ALLOWED_HOSTS=localhost,127.0.0.1
```

With `DEBUG=True`, Django automatically uses SQLite — no database setup needed.

### 4. Initialize the Database

```bash
python manage.py migrate
python manage.py createsuperuser   # optional — creates an admin account
python manage.py seed_data         # optional — loads sample restaurants
```

### 5. Run the App

Start the Django development server:

```bash
source .venv/bin/activate
python manage.py runserver
```

Open **http://localhost:8000** in your browser. Django serves both the API and the web interface.

---

## Environment Variables

All configuration is driven by environment variables (via `python-decouple`). Defaults are tuned for local development.

| Variable | Default | Description |
|---|---|---|
| `DEBUG` | `False` | Set `True` for local development (uses SQLite, verbose errors) |
| `SECRET_KEY` | insecure dev key | Django secret key — **must override in production** |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated allowed hosts |
| `DB_ENGINE` | `django.db.backends.postgresql` | Database engine (prod only, ignored when `DEBUG=True`) |
| `DB_NAME` | `nomz_db` | Database name |
| `DB_USER` | `postgres` | Database user |
| `DB_PASSWORD` | *(empty)* | Database password |
| `DB_HOST` | `localhost` | Database host |
| `DB_PORT` | `5432` | Database port |
| `USE_S3` | `False` | Enable AWS S3 for static/media files |
| `AWS_ACCESS_KEY_ID` | — | AWS credentials (when `USE_S3=True`) |
| `AWS_SECRET_ACCESS_KEY` | — | AWS credentials |
| `AWS_STORAGE_BUCKET_NAME` | — | S3 bucket name |
| `AWS_S3_REGION_NAME` | `us-east-1` | S3 bucket region |
| `AWS_S3_CUSTOM_DOMAIN` | `<bucket>.s3.amazonaws.com` | Optional CDN/custom S3 domain for static/media URLs |
| `MAX_UPLOAD_IMAGE_MB` | `10` | Max image upload size used by Django upload limits |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000,...` | Comma-separated CORS origins |
| `CSRF_TRUSTED_ORIGINS` | `http://localhost:8000,...` | Comma-separated trusted CSRF origins |
| `EMAIL_HOST_USER` | *(empty)* | SMTP user (e.g. Gmail address for password reset emails) |
| `EMAIL_HOST_PASSWORD` | *(empty)* | SMTP password / app password |

---

## Running Tests

```bash
# Activate virtual environment
source .venv/bin/activate

# Run Django tests with coverage
coverage run --source='nomz' manage.py test --verbosity=2

# View coverage report
coverage report

# Lint checks
black --check .
flake8 .

# Django system checks
python manage.py check
```

---

## CI/CD Pipeline

The project uses **Travis CI** with the following stages:

1. **Test** (on `develop`, `production`, `main`):
   - Runs PostgreSQL service
   - Installs Python dependencies
   - Runs migrations → test suite → `black` → `flake8` → `manage.py check`
   - Reports coverage to Coveralls

2. **Deploy** (on `production` branch only):
   - Deploys to AWS Elastic Beanstalk (`nomz-app` / `nomz-prod`)

---

## Deployment

The app is deployed on **AWS Elastic Beanstalk** with:

- **Web server:** Gunicorn via `Procfile`
- **Instance type:** t3.micro
- **Health check:** `/health/` endpoint
- **Static files:** Nginx serves `/static/` from `staticfiles/`
- **Container commands** (run on deploy):
  1. `python scripts/create_db.py` — ensures the RDS database exists
  2. `python manage.py migrate --noinput`
  3. `python manage.py collectstatic --noinput`

Production environment variables (`SECRET_KEY`, `DB_*`, `AWS_*`, `CSRF_TRUSTED_ORIGINS`, etc.) are configured in the Elastic Beanstalk environment settings.

---

## API Endpoints

All API endpoints are prefixed with `/api/` and use Django session authentication.

| Group | Endpoints |
|---|---|
| **Auth** | `auth/session/`, `auth/register/`, `auth/login/`, `auth/logout/`, `auth/admin-login/`, `auth/2fa/verify/`, `auth/password-reset/`, `auth/password-reset/confirm/` |
| **Search & Discovery** | `search/`, `restaurants/<id>/`, `restaurants/map-data/`, `recommendations/` |
| **Reviews** | `restaurants/<id>/review/`, `reviews/<id>/respond/` |
| **Restaurant Management** | `restaurant/profile/`, `restaurant/availability/`, `restaurant/communication/`, `restaurant/activation/`, `restaurant/photos/*` |
| **Diner** | `diner/preferences/`, `diner/account/` |
| **Messaging** | `messages/conversations/`, `messages/conversations/start/`, `messages/conversations/<id>/`, `messages/conversations/<id>/send/` |
| **Friends Chat** | `friends-chat/`, `friends-chat/<id>/`, `friends-chat/group/create/`, `friends-chat/group/<id>/manage/`, `friends-chat/<id>/recommend/`, `friends-chat/<id>/toggle-shared/` |
| **Claims** | `restaurant-claim/` |
| **Reporting** | `report/` |
| **Admin** | `admin/dashboard-summary/`, `admin/pending-approvals/`, `admin/approved-restaurants/`, `admin/rejected-restaurants/`, `admin/approve/<id>/`, `admin/reject/<id>/`, `admin/moderation/`, `admin/users/`, `admin/login-logs/`, `admin/recalculate-scores/`, `admin/score-anomalies/` |
