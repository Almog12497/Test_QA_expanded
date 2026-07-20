import json
import pytest
from src.testing.test_framework import AmmeterTestFramework


FAKE_RESULT = {
    "run_id": "abcd1234-0000-0000-0000-000000000000",
    "ammeter_type": "greenlee",
    "started_at": "2026-01-01T10:00:00",
    "completed_at": "2026-01-01T10:00:10",
    "config": {"measurements_count": 3, "sampling_frequency_hz": 1.0},
    "samples": [1.0, 2.0, 3.0],
    "statistics": {
        "mean": 2.0, "median": 2.0, "std_dev": 1.0,
        "min": 1.0, "max": 3.0, "count": 3,
    },
}


@pytest.fixture
def framework(tmp_path):
    fw = AmmeterTestFramework()
    fw.results_dir = tmp_path
    return fw


def test_archive_creates_json_file(framework, tmp_path):
    framework._archive_result(FAKE_RESULT)
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_archive_filename_contains_type_and_short_id(framework, tmp_path):
    framework._archive_result(FAKE_RESULT)
    filename = list(tmp_path.glob("*.json"))[0].name
    assert "greenlee" in filename
    assert "abcd" in filename


def test_archive_content_is_readable_and_correct(framework, tmp_path):
    framework._archive_result(FAKE_RESULT)
    path = list(tmp_path.glob("*.json"))[0]
    data = json.loads(path.read_text())
    assert data["ammeter_type"] == "greenlee"
    assert data["statistics"]["mean"] == pytest.approx(2.0)
    assert data["statistics"]["count"] == 3


def test_load_result_by_short_prefix(framework):
    framework._archive_result(FAKE_RESULT)
    loaded = framework.load_result("abcd")
    assert loaded["run_id"] == FAKE_RESULT["run_id"]


def test_load_result_not_found_raises(framework):
    with pytest.raises(FileNotFoundError):
        framework.load_result("xxxx")


def test_load_result_corrupted_json_raises_value_error(framework, tmp_path):
    (tmp_path / "greenlee_20260101_100000_abcd.json").write_text("{ not valid json")
    with pytest.raises(ValueError, match="Could not read result file"):
        framework.load_result("abcd")


def test_list_results_empty_dir(framework):
    results = framework.list_results()
    assert results == []


def test_list_results_returns_one_entry(framework):
    framework._archive_result(FAKE_RESULT)
    results = framework.list_results()
    assert len(results) == 1
    assert results[0]["ammeter_type"] == "greenlee"


def test_list_results_filters_by_ammeter_type(framework):
    entes_result = {
        **FAKE_RESULT,
        "run_id": "efgh5678-0000-0000-0000-000000000000",
        "ammeter_type": "entes",
    }
    framework._archive_result(FAKE_RESULT)
    framework._archive_result(entes_result)

    greenlee_only = framework.list_results("greenlee")
    assert len(greenlee_only) == 1
    assert greenlee_only[0]["ammeter_type"] == "greenlee"


def test_list_results_skips_corrupted_file(framework, tmp_path):
    framework._archive_result(FAKE_RESULT)
    (tmp_path / "corrupted_test.json").write_text("{ bad json !!!")
    results = framework.list_results()
    assert len(results) == 1  # corrupted file is skipped, valid one is returned


def test_compare_results_prints_stats_table(framework, capsys):
    entes_result = {
        **FAKE_RESULT,
        "run_id": "efgh5678-0000-0000-0000-000000000000",
        "ammeter_type": "entes",
    }
    framework._archive_result(FAKE_RESULT)
    framework._archive_result(entes_result)
    framework.compare_results(["abcd", "efgh"])
    output = capsys.readouterr().out
    assert "Mean" in output
    assert "Std dev" in output
