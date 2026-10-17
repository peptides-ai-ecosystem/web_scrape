"""Give every test the marker of its theme folder (``tests/<theme>/``), so ``pytest -m vendors`` works."""

import pytest

THEMES = {"pep_pedia", "vendors", "sync", "evaluation", "ops"}


def pytest_collection_modifyitems(items):
    for item in items:
        theme = item.path.parent.name
        if theme in THEMES:
            item.add_marker(getattr(pytest.mark, theme))
