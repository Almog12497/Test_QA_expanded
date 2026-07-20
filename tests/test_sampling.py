import pytest
from unittest.mock import patch
from src.testing.test_framework import AmmeterTestFramework

# Patch the client where it is imported inside test_framework, not where it is defined
_CLIENT = "src.testing.test_framework.request_current_from_ammeter"


@pytest.fixture
def framework(tmp_path):
    fw = AmmeterTestFramework()
    fw.results_dir = tmp_path
    return fw


_FAST = {"measurements_count": 3, "sampling_frequency_hz": 100}


def test_run_test_collects_samples_from_client(framework):
    with patch(_CLIENT, return_value=2.5) as mock_client:
        result = framework.run_test("greenlee", **_FAST)
    assert result["samples"] == [2.5, 2.5, 2.5]
    assert mock_client.call_count == 3


def test_run_test_connection_refused_returns_empty_samples(framework):
    with patch(_CLIENT, side_effect=ConnectionRefusedError):
        result = framework.run_test("greenlee", **_FAST)
    assert result["samples"] == []


def test_run_test_connection_refused_skips_archive(framework, tmp_path):
    with patch(_CLIENT, side_effect=ConnectionRefusedError):
        framework.run_test("greenlee", **_FAST)
    assert list(tmp_path.glob("*.json")) == []


def test_run_test_connection_refused_returns_empty_statistics(framework):
    with patch(_CLIENT, side_effect=ConnectionRefusedError):
        result = framework.run_test("greenlee", measurements_count=1)
    assert result["statistics"] == {}


def test_run_test_partial_failures_collects_successful_samples(framework):
    # Second call raises, first and third succeed
    with patch(_CLIENT, side_effect=[2.5, ConnectionRefusedError(), 3.0]):
        result = framework.run_test("greenlee", **_FAST)
    assert result["samples"] == [2.5, 3.0]


def test_run_test_generates_unique_run_ids(framework):
    with patch(_CLIENT, return_value=1.0):
        result1 = framework.run_test("greenlee", measurements_count=1)
        result2 = framework.run_test("greenlee", measurements_count=1)
    assert result1["run_id"] != result2["run_id"]


def test_run_test_result_has_expected_keys(framework):
    with patch(_CLIENT, side_effect=ConnectionRefusedError):
        result = framework.run_test("greenlee", measurements_count=1)
    for key in ("run_id", "ammeter_type", "started_at", "completed_at", "samples", "statistics"):
        assert key in result
