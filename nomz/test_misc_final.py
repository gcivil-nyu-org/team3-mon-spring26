"""Small miscellaneous tests (e.g. repo-root scripts)."""

import pytest


@pytest.mark.django_db
def test_seed_data_main_runs():
    """Execute ``seed_data.main()`` once for coverage (rolls back with django_db)."""
    import seed_data

    seed_data.main()
