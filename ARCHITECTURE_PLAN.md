# NYC Restaurant Map - Comprehensive Architecture Plan

## Executive Summary

Your current stack is **Django 6.0.2** with **PostgreSQL**, deployed on **AWS Elastic Beanstalk**. We'll build a cost-effective data ingestion pipeline using **AWS Lambda + EventBridge** and create a **GeoDjango + Leaflet.js** front-end for the interactive map.

---

## Part 1: Current Tech Stack Analysis

### What You Have
- **Backend**: Django 6.0.2 + Django REST Framework
- **Database**: PostgreSQL (local SQLite for dev, AWS RDS for prod)
- **Frontend**: Bootstrap 5.3 with custom Teal/Red color scheme (#FF6B6B, #4ECDC4)
- **Deployment**: AWS Elastic Beanstalk
- **Authentication**: Django's built-in auth with custom `UserProfile` (roles: diner/restaurant)
- **Cloud Dependencies**: boto3, django-storages already in requirements.txt

### Dependencies
- `pandas` and `numpy` (for data transformation)
- `django-cors-headers` (CORS already enabled)
- `psycopg2-binary` (PostgreSQL driver)
- `docutils` and other supporting libraries

---

## Part 2: AWS Data Ingestion Architecture

### Challenge
Fetch data from 3 Socrata/NYC OpenData endpoints and sync daily while keeping costs low.

### Solution: Lambda + EventBridge + RDS

```
EventBridge (Scheduled Event at 2 AM UTC daily)
    ↓
Lambda Function (Python 3.11, 15 min timeout)
    ├→ Fetch from 3 Socrata endpoints (via HTTP)
    ├→ Clean & normalize data
    ├→ Merge datasets by name/address/ZIP matching
    ├→ Store in RDS PostgreSQL
    └→ Log to CloudWatch
```

### Cost Breakdown
- **Lambda**: ~1 invocation/day × $0.20/million = negligible
- **Outbound Data Transfer**: ~100-200 MB/day = ~$0.02/day
- **RDS**: Shared by web app, marginal increase
- **Total**: ~$0.70/month incremental

### Why NOT...
- ❌ **EC2**: Always running, costs $10-30/month
- ❌ **Glue**: Overkill complexity, $0.44/DPU-hour
- ❌ **Step Functions**: Unnecessary orchestration
- ✅ **Lambda**: Serverless, pay-per-invocation

---

## Part 3: Data Modeling & Merging Strategy

### 3A: Database Schema (PostgreSQL + GeoDjango)

We need **5 core models**:

#### 1. **Restaurant** (Main Entity)
```
- id (PK)
- name (CharField, 255)
- address (CharField, 255)
- borough (CharField, e.g., "Manhattan")
- zip_code (CharField)
- phone (CharField, nullable)
- website (URLField, nullable)
- cuisine_types (JSONField - list of strings)
- location (PointField - SRID 4326) ← GeoDjango
- created_at (DateTimeField)
- updated_at (DateTimeField)
- composite_score (FloatField, 0-100) ← Calculated
- master_id (CharField, unique, nullable) ← For deduplication
```

#### 2. **RestaurantDataSource** (Track origins)
```
- id (PK)
- restaurant (ForeignKey)
- source (CharField: "EATERIES" | "DINING_OUT" | "INSPECTIONS")
- external_id (CharField, 100)
- external_name (CharField, 255)
- source_data (JSONField) ← Raw API response
- synced_at (DateTimeField)
```

#### 3. **InspectionRecord** (DOHMH data)
```
- id (PK)
- restaurant (ForeignKey)
- inspection_date (DateField)
- grade (CharField: "A" | "B" | "C" | "Not Yet Graded")
- score (IntegerField, 0-100)
- violation_count (IntegerField)
- critical_violation_count (IntegerField)
- violations (JSONField - list of violation descriptions)
- url (URLField, nullable)
```

#### 4. **DiningOutLocation** (Dining Out specific)
```
- id (PK)
- restaurant (ForeignKey)
- location_type (CharField: "Indoor" | "Outdoor")
- opening_date (DateField, nullable)
- closing_date (DateField, nullable)
- capacity (IntegerField, nullable)
```

#### 5. **DataSyncLog** (Audit trail)
```
- id (PK)
- source (CharField)
- sync_date (DateTimeField)
- records_fetched (IntegerField)
- records_merged (IntegerField)
- records_created (IntegerField)
- records_updated (IntegerField)
- errors (JSONField, nullable)
- latency_ms (IntegerField)
```

### 3B: Matching Strategy (Entity Resolution)

**Problem**: Three datasets don't share a unique ID, some records are duplicates.

**Solution**: Multi-layered matching algorithm

```python
Priority Order (Best → Worst):
1. Exact match on (name, address, zip)
   - Normalize: uppercase, strip whitespace/punctuation
   
2. Fuzzy match on name + address similarity (>90%)
   - Use difflib.SequenceMatcher
   - Must match ZIP or be within 0.1 miles
   
3. Fuzzy match on name + ZIP + borough
   - Threshold: 85% similarity
   
4. Create as new restaurant if no match

Store all original source data in RestaurantDataSource for audit trail.
```

Example:
```
EATERIES:
  - "PIZZA PALACE LLC"
  - "123 Main St"
  - "10001"

DINING_OUT:
  - "Pizza Palace"
  - "123 Main Street"
  - "10001"

INSPECTIONS:
  - "PIZZA PALACE"
  - "123 MAIN ST"
  - "10001"

Result: All 3 merge into 1 Restaurant with 3 RestaurantDataSource records
```

---

## Part 4: Composite Score Algorithm

### Scoring Methodology

The composite score combines **inspection grades**, **violation severity**, and **recency**.

```
Composite Score = (0.50 × Grade Score) + (0.35 × Violation Score) + (0.15 × Recency Score)

Range: 0-100 (higher is better)
```

### Component 1: Grade Score (50%)
```
Grade A → 95 points
Grade B → 70 points
Grade C → 40 points
Not Yet Graded → 60 points (neutral)
No Records → 50 points (unknown)
```

### Component 2: Violation Score (35%)
```
Base: 100 points
Deductions:
  - Each critical violation: -2 points
  - Each non-critical violation: -0.5 points
  - Total violations count > 5: additional -5 points

Score = max(0, 100 - deductions)
```

### Component 3: Recency Score (15%)
```
Days since last inspection: D
If D < 30 days:   100 points (recently inspected)
If D < 90 days:   85 points
If D < 180 days:  70 points
If D < 365 days:  55 points
If D >= 365 days: 30 points (outdated)
If no records:    0 points

Decay factor applies: older grades count less
```

### Calculation Example
```
Restaurant X:
- Latest grade: A (95 points)
- Critical violations: 0
- Non-critical violations: 2 → 100 - 1 = 99 points
- Last inspected: 20 days ago → 100 points

Composite = (0.50 × 95) + (0.35 × 99) + (0.15 × 100)
          = 47.5 + 34.65 + 15
          = 97.15 → Rounded to 97
```

### Edge Cases
- No inspection data: Score = 50 (neutral)
- Multiple grades (pick most recent): Use latest
- Grade change in period: Trend indicator can be a separate field

---

## Part 5: Front-End Map Component

### Library Choice: **Leaflet.js** (NOT Google Maps or Mapbox)

**Why Leaflet?**
| Feature | Leaflet | Google Maps | Mapbox |
|---------|---------|-------------|--------|
| Cost | Free | $7/1000 loads | $0.50/1000 loads |
| Bundle Size | 40KB | 200KB | 150KB |
| Offline Maps | Yes | No | No |
| License | MIT (Free) | Commercial | Commercial |
| Learning Curve | Easy | Easy | Medium |
| Bootstrap Integration | Perfect | Good | Good |

We'll use **OpenStreetMap tiles** (free, no API key needed).

### Map UI Component Features

```
┌─────────────────────────────────────────┐
│ [Map Container - Full Responsive]       │
├─────────────────────────────────────────┤
│ Search Bar | Filter Dropdown | List View│
├─────────────────────────────────────────┤
│                                         │
│  [Interactive Map with Markers]         │
│  - Color-coded by score (Red/Yellow/Green)│
│  - Cluster markers when zoomed out      │
│  - Popup on hover/click with details    │
│                                         │
└─────────────────────────────────────────┘

Sidebar (Mobile: Hidden, Desktop: Visible):
  - Selected restaurant details
  - Inspection history
  - Violation breakdown
  - Link to full details page
```

### Marker Color Coding
```
Score 80-100: Green (#27AE60)
Score 60-79:  Yellow (#F39C12)
Score <60:    Red (#E74C3C)
Grade on hover: Quick visual indicator
```

### Technologies
- **Frontend Map**: Leaflet.js 1.9.4 + Leaflet.markercluster
- **Data Binding**: Vanilla JS (no React needed, keep it simple)
- **AJAX**: Fetch API for restaurant data
- **Templates**: Django template with embedded map initialization

---

## Part 6: API Endpoints (Django REST Framework)

We'll add REST endpoints for mobile/JS consumption:

```
GET  /api/restaurants/
     - Query params: [lat, lon, radius], [borough], [cuisine], [min_score]
     - Returns: GeoJSON format for map
     
GET  /api/restaurants/<id>/
     - Returns: Full restaurant detail + inspection history

GET  /api/restaurants/<id>/inspections/
     - Returns: List of all inspection records

GET  /api/restaurants/nearby/<lat>/<lon>/
     - Returns: 10 nearest restaurants (PostGIS query)

POST /api/restaurants/<id>/favorite/
     - Requires: auth, saves to user profile

GET  /api/statistics/
     - Borough-level stats, average scores, etc.
```

---

## Part 7: Lambda Function Structure

```
aws-lambda/
  ├── ingestion_lambda.py (Main handler)
  ├── requirements.txt (pandas, requests, psycopg2-binary)
  ├── socrata/
  │   ├── eateries_importer.py
  │   ├── dining_out_importer.py
  │   └── inspections_importer.py
  └── utils/
      ├── entity_resolver.py (Matching logic)
      ├── data_cleaner.py (Normalization)
      └── score_calculator.py (Composite score)
```

---

## Part 8: Implementation Roadmap

### Phase 1: Database & Models (Week 1)
1. ✅ Update models.py with all 5 models + GeoDjango
2. ✅ Add PostGIS extension to PostgreSQL
3. ✅ Write migrations
4. ✅ Create management command to test locally

### Phase 2: Socrata Importers (Week 1-2)
5. ✅ Create eateries_importer.py
6. ✅ Create dining_out_importer.py
7. ✅ Create inspections_importer.py
8. ✅ Write entity resolver (matching logic)

### Phase 3: Lambda Deployment (Week 2)
9. ✅ Package Lambda function + Dockerfile
10. ✅ Set up EventBridge schedule
11. ✅ Create CloudWatch logs monitoring

### Phase 4: REST APIs (Week 3)
12. ✅ Implement Django REST Framework viewsets
13. ✅ Add GeoJSON serialization
14. ✅ Add filtering/search

### Phase 5: Front-End Map (Week 3-4)
15. ✅ Create map.html template
16. ✅ Integrate Leaflet.js
17. ✅ Build search/filter UI
18. ✅ Connect to REST APIs
19. ✅ Responsive design for mobile

### Phase 6: Styling & Deployment (Week 4)
20. ✅ Match existing design system
21. ✅ Test on AWS Elastic Beanstalk
22. ✅ Load testing

---

## Part 9: File Structure (New Files to Create)

```
nomz/
  ├── models.py (UPDATED)
  ├── views.py (UPDATED)
  ├── urls.py (UPDATED)
  ├── forms.py (unchanged)
  ├── serializers.py (NEW - DRF serializers)
  ├── api_views.py (NEW - REST endpoints)
  ├── management/
  │   └── commands/
  │       ├── import_eateries.py (NEW)
  │       ├── import_dining_out.py (NEW)
  │       └── import_inspections.py (NEW)
  └── utils/
      ├── entity_resolver.py (NEW)
      ├── score_calculator.py (NEW)
      └── socrata_client.py (NEW)

templates/nomz/
  ├── map.html (NEW)
  ├── restaurant_detail.html (NEW)

aws-lambda/
  ├── lambda_function.py (NEW)
  ├── requirements.txt (NEW)
  └── ... (utilities)

MIGRATIONS/
  └── 0002_restaurant_models.py (AUTO GENERATED)
```

---

## Part 10: Dependencies to Add

```
# Add to requirements.txt under existing packages:
django-gis>=3.12  # GeoDjango (requires PostGIS)
django-rest-framework-gis>=0.16  # GeoJSON support
requests>=2.31.0  # HTTP for Socrata API
fuzzywuzzy>=0.18.0  # String matching
python-Levenshtein>=0.21.0  # Faster fuzzy matching
Shapely>=2.0.0  # Geospatial operations
folium>=0.14.0  # Optional: Map preview in admin
```

---

## Part 11: Key Design Decisions

| Decision | Why |
|----------|-----|
| **Leaflet.js not Google Maps** | Free, lightweight, open-source |
| **PostGIS not plain PostgreSQL** | Spatial queries (nearest restaurants, radius search) |
| **Lambda not Celery** | No always-on server needed, cheaper |
| **EventBridge not Cron** | AWS-native, integrates seamlessly |
| **Entity resolver before DB** | Cleaner schema, easier to maintain |
| **Composite score stored in DB** | Fast queries without recalculation |
| **JSONField for inspection records** | Flexible schema, no need for more tables |

---

## Next Steps

**Ready to implement?** Let me know which part to tackle first:

1. ✏️ **Start with Models** - Define database schema
2. 🔄 **Start with Importers** - Write Socrata API clients
3. 🎨 **Start with Frontend** - Build map interface
4. ☁️ **Start with Lambda** - Set up AWS pipeline

I recommend **starting with Models (Part 1)**, then **Socrata clients (Part 2)**, as they're independent and provide the foundation for everything else.

---

## Questions for Clarification

Before we code, confirm:
1. Do you have **PostGIS installed** on your RDS instance? (We may need to enable it)
2. Should the map default to **all of Manhattan** or a specific area?
3. Do you want a **detail page** for each restaurant, or just popups on the map?
4. Should **users be able to favorite restaurants**? (Requires DB change)
5. Do you want the Lambda to run **daily at 2 AM**, or a different schedule?

---
