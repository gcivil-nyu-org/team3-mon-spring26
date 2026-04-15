from unittest.mock import patch

from django.test import TestCase

from nomz.forms import AdminLoginForm


class FormsCoverageTests(TestCase):
    def test_admin_login_form_clean_bootstraps_admin_user_flags_and_backend(self):
        """
        Targets forms.py lines 128-145.
        """
        form = AdminLoginForm(
            request=None,
            data={
                "username": "admin",
                "password": "irrelevant-when-patched",
                "security_code": "ADM123",
            },
        )

        with patch("django.contrib.auth.hashers.check_password", return_value=True), patch(
            "decouple.config", return_value="ADM123"
        ):
            assert form.is_valid() is True

        user = form.get_user()
        assert user.username == "admin"
        assert user.is_staff is True
        assert user.is_superuser is True
        assert user.is_active is True
        assert getattr(user, "backend", None) == "django.contrib.auth.backends.ModelBackend"
