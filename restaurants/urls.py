from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from two_factor.urls import urlpatterns as tf_urls
from django.views.generic import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),
    # Redirect Django auth → signin (HTML)
    path("login/", RedirectView.as_view(url="/signin/", permanent=False)),
    path("account/login/", RedirectView.as_view(url="/signin/", permanent=False)),
    # API + HTML routes
    path("", include("nomz.urls")),
    # two-factor routes
    path("", include(tf_urls)),
]

# Serve user-uploaded media files in local development.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
