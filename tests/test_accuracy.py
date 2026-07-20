import pytest
from src.testing.test_framework import AmmeterTestFramework


def _make_result(run_id, ammeter_type, mean, std_dev, samples):
    return {
        "run_id": run_id,
        "ammeter_type": ammeter_type,
        "started_at": "2026-01-01T10:00:00",
        "completed_at": "2026-01-01T10:00:10",
        "config": {"measurements_count": len(samples), "sampling_frequency_hz": 1.0},
        "samples": samples,
        "statistics": {
            "mean": mean,
            "median": mean,
            "std_dev": std_dev,
            "min": min(samples),
            "max": max(samples),
            "count": len(samples),
        },
    }


@pytest.fixture
def framework_with_two_results(tmp_path):
    fw = AmmeterTestFramework()
    fw.results_dir = tmp_path
    # greenlee: CV = 0.01 / 1.0 = 0.01 (precise)
    fw._archive_result(_make_result(
        "aaaa0000-0000-0000-0000-000000000000", "greenlee",
        mean=1.0, std_dev=0.01, samples=[0.99, 1.0, 1.01],
    ))
    # entes: CV = 1.0 / 2.0 = 0.5 (noisy)
    fw._archive_result(_make_result(
        "bbbb0000-0000-0000-0000-000000000000", "entes",
        mean=2.0, std_dev=1.0, samples=[1.0, 2.0, 3.0],
    ))
    return fw


def test_accuracy_assessment_ranks_lower_cv_first(framework_with_two_results):
    assessments = framework_with_two_results.accuracy_assessment(["aaaa", "bbbb"])
    assert assessments[0]["ammeter_type"] == "greenlee"
    assert assessments[1]["ammeter_type"] == "entes"


def test_accuracy_assessment_cv_values_are_correct(framework_with_two_results):
    assessments = framework_with_two_results.accuracy_assessment(["aaaa", "bbbb"])
    assert assessments[0]["cv"] == pytest.approx(0.01 / 1.0)
    assert assessments[1]["cv"] == pytest.approx(1.0 / 2.0)


def test_accuracy_assessment_winner_has_lowest_cv(framework_with_two_results):
    assessments = framework_with_two_results.accuracy_assessment(["aaaa", "bbbb"])
    cvs = [a["cv"] for a in assessments]
    assert cvs == sorted(cvs)


def test_accuracy_assessment_no_results_returns_none(tmp_path):
    fw = AmmeterTestFramework()
    fw.results_dir = tmp_path
    result = fw.accuracy_assessment()
    assert result is None


def test_accuracy_assessment_skips_corrupted_json(framework_with_two_results, tmp_path):
    (tmp_path / "corrupted_test.json").write_text("{ bad json")
    # Should still return results for the two valid files
    assessments = framework_with_two_results.accuracy_assessment()
    assert len(assessments) == 2
