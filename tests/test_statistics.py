import pytest
from src.testing.test_framework import AmmeterTestFramework


@pytest.fixture
def framework():
    return AmmeterTestFramework()


def test_compute_stats_basic(framework):
    stats = framework._compute_stats([1.0, 2.0, 3.0, 4.0, 5.0])
    assert stats["mean"] == pytest.approx(3.0)
    assert stats["median"] == pytest.approx(3.0)
    assert stats["min"] == pytest.approx(1.0)
    assert stats["max"] == pytest.approx(5.0)
    assert stats["count"] == 5
    assert stats["std_dev"] > 0


def test_compute_stats_single_sample(framework):
    stats = framework._compute_stats([2.5])
    assert stats["mean"] == pytest.approx(2.5)
    assert stats["median"] == pytest.approx(2.5)
    assert stats["min"] == pytest.approx(2.5)
    assert stats["max"] == pytest.approx(2.5)
    assert stats["std_dev"] == 0.0
    assert stats["count"] == 1


def test_compute_stats_empty_returns_empty_dict(framework):
    assert framework._compute_stats([]) == {}


def test_compute_stats_identical_values(framework):
    stats = framework._compute_stats([1.5, 1.5, 1.5])
    assert stats["mean"] == pytest.approx(1.5)
    assert stats["std_dev"] == pytest.approx(0.0)
    assert stats["min"] == pytest.approx(1.5)
    assert stats["max"] == pytest.approx(1.5)


def test_compute_stats_known_std_dev(framework):
    # mean=2, std_dev of [1,2,3] with sample std_dev = 1.0
    stats = framework._compute_stats([1.0, 2.0, 3.0])
    assert stats["std_dev"] == pytest.approx(1.0)
