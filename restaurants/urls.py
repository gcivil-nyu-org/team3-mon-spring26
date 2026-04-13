from django.contrib import admin
from django.urls import path, include, re_path
from two_factor.urls import urlpatterns as tf_urls
from django.views.generic import RedirectView

from nomz.spa_shell_views import spa

urlpatterns = [
    path("admin/", admin.site.urls),
    # Redirect Django auth → React
    path("login/", RedirectView.as_view(url="/signin/", permanent=False)),
    path("account/login/", RedirectView.as_view(url="/signin/", permanent=False)),
    # API + SPA routes (nomz.urls has both; API routes prefixed with "api/", catch-all at end)
    path("", include("nomz.urls")),
    # two-factor routes (if still needed)
    path("", include(tf_urls)),
    # ✅ CRITICAL: React SPA catch-all (MUST BE LAST)
    re_path(r"^.*$", spa),
]
