import pytest
from pathlib import Path


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Temporary data directory for test isolation."""
    return tmp_path / "data"


@pytest.fixture
def sample_market():
    """A realistic Market object for testing."""
    from polymarket_predictor.scrapers.polymarket import Market

    return Market(
        id="12345",
        question="Will Bitcoin be above $72,000 on March 25?",
        slug="bitcoin-above-72k-on-march-25",
        outcomes=[{"name": "Yes", "price": 0.65}, {"name": "No", "price": 0.35}],
        volume=50000.0,
        category="Crypto",
        active=True,
        closed=False,
        created_at=None,
        end_date=None,
        resolution=None,
    )
