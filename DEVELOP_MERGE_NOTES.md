# Merge Notes: forgetPass_EmailConfig-john ↔ develop

Use this when merging **develop** into **forgetPass_EmailConfig-john** (or the other way around).

## What was aligned on this branch for develop compatibility

- **`/health/`** – Added in `nomz/views.health_check` and `nomz/urls`. Matches develop and `.ebextensions` `HealthCheckPath: /health/` so EB health checks work.
- **`.ebextensions/django.config`** – `HealthCheckPath: /health/` added so it matches develop.

## Develop changes that affect this branch when you merge

### 1. `restaurants/urls.py` (develop)

Develop adds **django-two-factor-auth** and overrides the top-level `login`:

- `path('login/', RedirectView.as_view(pattern_name='two_factor:login', ...), name='login')`
- `path('', include(tf_urls))` before `path('', include('nomz.urls'))`

**Effect on password reset:**  
`password_reset`, `password_reset_done`, `password_reset_confirm`, and `password_reset_complete` stay in **nomz/urls.py** and are unchanged. Links that use `{% url 'login' %}` (e.g. “Forgot password?” and redirect after reset) will go to **2FA login** after the merge, not to `nomz.views.user_login`. Your reset flow itself is not broken; only the final “back to login” destination becomes 2FA.

**If you want “back to login” to go to simple login:**  
After merging, you can either keep 2FA as the main login and leave as-is, or add a separate named URL (e.g. `simple_login`) in `nomz/urls.py` and use that in reset templates instead of `login`.

### 2. `restaurants/settings.py` (develop)

Develop adds:

- `django_otp`, `django_otp.plugins.otp_totp`, `django_otp.plugins.otp_static`, `two_factor` to `INSTALLED_APPS`
- `django_otp.middleware.OTPMiddleware` in `MIDDLEWARE`
- `'nomz'` → `'nomz.apps.NomzConfig'`

No conflict with your email/password-reset settings (EMAIL_*, LOGIN_*, etc.). Keep your `.env` and email config; merge the new apps and middleware from develop.

### 3. Migrations (develop) and commit 46078c2

Develop adds:

- Multiple `0002_*` migrations (e.g. restaurant, restaurantphoto, loginlog, NYC ingestion)
- `0003_*`, `0004_alter_restaurant_owner`, `0004_merge_20260308_2129`, `0005_merge_20260308_2231`, `0006_restaurantsearch`

This branch only has `0001_initial` (UserProfile). When you merge develop:

1. Take develop’s migration files and the merge migrations as-is.
2. Run `python manage.py migrate` after merge.
3. If Django reports conflicting migration heads, run `makemigrations --merge` and commit the merge migration, then migrate again.

Your password reset and email code do not add migrations; they work with the existing User model and your settings.

### 4. nomz/urls.py (develop)

Develop adds: `health/` (already added here), `map/`, `api/restaurants/map-data/`, restaurant profile/photo routes, `search/`.  
Password reset paths are the same. When merging, keep both your password-reset routes and develop’s new routes.

## Summary

| Area           | Breaks password reset? | Action on merge |
|----------------|------------------------|-----------------|
| `/health/`     | No                     | Already added on this branch. |
| restaurants/urls (2FA, `login`) | No (reset flow works; “login” becomes 2FA) | Accept develop’s urls; optionally add `simple_login` in nomz if you want a non-2FA link from reset. |
| settings (OTP, NomzConfig) | No | Merge develop’s INSTALLED_APPS and MIDDLEWARE; keep your email/LOGIN_* settings. |
| Migrations     | No                     | Use develop’s migrations; run `migrate` (and `makemigrations --merge` if needed). |
| nomz/urls      | No                     | Merge; keep all password-reset paths and new develop paths. |

Your password reset and email module remain compatible with develop; only the meaning of the `login` URL name changes to 2FA after the merge.
