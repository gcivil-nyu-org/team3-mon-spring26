from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory

import pytest
from django.conf import settings
from django.http import Http404
from django.test import TestCase, override_settings
from django.test.client import RequestFactory

from nomz import spa_shell_views


@pytest.mark.django_db
class SpaShellViewsTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @override_settings(DEBUG=True)
    def test_load_index_bytes_embedded_fallback_when_no_index_exists(self):
        req = self.factory.get("/?next=/dashboard")
        req.user = SimpleNamespace(is_authenticated=False)
        with self.settings(FRONTEND_DIST_DIR=Path(settings.BASE_DIR) / "does-not-exist-xyz"):
            data = spa_shell_views._load_index_bytes()
        self.assertIn(b"Frontend bundle not found", data)

    @override_settings(DEBUG=True)
    def test_spa_index_serves_dist_file_when_present(self):
        with TemporaryDirectory() as tmp:
            with self.settings(FRONTEND_DIST_DIR=tmp):
                dist_dir = Path(tmp)
                index = dist_dir / "index.html"
                index.write_bytes(b"<html><body>dist-index</body></html>")
                req = self.factory.get("/?next=/profile")
                req.user = SimpleNamespace(is_authenticated=True)
                response = spa_shell_views.spa_index(req)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Cache-Control"], "no-store, max-age=0")
                self.assertIn(b"dist-index", response.content)

    @override_settings(DEBUG=False)
    def test_spa_index_returns_503_when_build_missing_in_non_debug(self):
        req = self.factory.get("/?next=/signin")
        req.user = SimpleNamespace(is_authenticated=False)
        with self.settings(FRONTEND_DIST_DIR=Path(settings.BASE_DIR) / "missing-spa-dist"):
            response = spa_shell_views.spa_index(req)
        self.assertEqual(response.status_code, 503)
        self.assertIn("Nomz UI build missing", response.content.decode("utf-8"))

    @override_settings(DEBUG=True)
    def test_spa_asset_blocks_path_traversal_and_missing_file(self):
        with TemporaryDirectory() as tmp:
            with self.settings(FRONTEND_DIST_DIR=tmp):
                assets_dir = Path(tmp) / "assets"
                assets_dir.mkdir(parents=True, exist_ok=True)
                req = self.factory.get("/assets/../secret.txt?next=/")
                req.user = SimpleNamespace(is_authenticated=True)
                with self.assertRaises(Http404):
                    spa_shell_views.spa_asset(req, "../secret.txt")

                with self.assertRaises(Http404):
                    spa_shell_views.spa_asset(req, "missing.js")

    @override_settings(DEBUG=True)
    def test_spa_asset_serves_file_with_cache_headers(self):
        with TemporaryDirectory() as tmp:
            with self.settings(FRONTEND_DIST_DIR=tmp):
                assets_dir = Path(tmp) / "assets"
                assets_dir.mkdir(parents=True, exist_ok=True)
                asset = assets_dir / "app.js"
                asset.write_text("console.log('ok');", encoding="utf-8")
                req = self.factory.get("/assets/app.js?next=/map")
                req.user = SimpleNamespace(is_authenticated=False)
                response = spa_shell_views.spa_asset(req, "app.js")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    response["Cache-Control"], "public, max-age=31536000, immutable"
                )
                self.assertIn(
                    response["Content-Type"],
                    {"text/javascript", "application/javascript"},
                )
                response.close()
