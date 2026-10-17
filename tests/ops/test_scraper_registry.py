"""Every dotted path in the scraper registry must import, and the registry names the two hosted scrapers."""
import importlib

import pytest

from app.scrapers.registry import SCRAPERS, get_scraper


def _resolve(path: str):
    parts = path.split(".")
    for i in range(len(parts), 0, -1):
        try:
            obj = importlib.import_module(".".join(parts[:i]))
        except ModuleNotFoundError:
            continue
        for attr in parts[i:]:
            obj = getattr(obj, attr)
        return obj
    raise ImportError(path)


def test_the_two_hosted_scrapers_are_registered():
    assert set(SCRAPERS) == {"pep_pedia", "vendors"}
    assert get_scraper("vendors").own_tables == ("vendor_scrape_targets", "vendor_price_observations")
    assert get_scraper("pep_pedia").writes == "platform"


@pytest.mark.parametrize("name", sorted(SCRAPERS))
def test_every_dotted_path_imports(name):
    info = SCRAPERS[name]
    for path in (info.discover, info.fetch, info.controller, *info.extract):
        assert _resolve(path) is not None, path
