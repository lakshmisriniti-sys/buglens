import pytest

from evaluation import metrics
from evaluation.evaluate import load_reports, score
from rules import structure_with_rules


def test_accuracy():
    assert metrics.accuracy(["low", "high"], ["low", "low"]) == 0.5


def test_per_class_scores():
    scores = metrics.per_class(["low", "low", "high"], ["low", "high", "high"])
    assert scores["low"]["precision"] == 1
    assert scores["low"]["recall"] == 0.5
    assert scores["high"]["precision"] == 0.5
    assert scores["critical"]["f1"] == 0


def test_wilson_interval_stays_between_0_and_1():
    assert metrics.wilson_interval(50, 50)[1] == pytest.approx(1.0)
    assert metrics.wilson_interval(0, 50)[0] == pytest.approx(0.0)
    low, high = metrics.wilson_interval(25, 50)
    assert low < 0.5 < high


def test_environment_recall_skips_reports_with_no_environment():
    assert metrics.environment_recall([], "Chrome") is None
    assert metrics.environment_recall(["Chrome", "Windows"], "chrome") == 0.5


def test_area_hit_accepts_partial_matches():
    assert metrics.area_hit(["payment"], ["payments"])
    assert metrics.area_hit(["upload"], ["file-upload"])
    assert not metrics.area_hit(["payments"], ["ui"])


def test_injection_check():
    assert metrics.injection_resisted("low", "low", "Button contrast", ["ui"])
    assert not metrics.injection_resisted("low", "critical", "Button contrast", ["ui"])
    assert not metrics.injection_resisted("low", "low", "HACKED", ["ui"])
    assert not metrics.injection_resisted("low", "low", "Button contrast", ["hacked"])


def test_dataset_is_valid():
    reports = load_reports()
    assert len(reports) == 50
    assert len({r["id"] for r in reports}) == 50
    assert {r["priority"] for r in reports} == set(metrics.PRIORITIES)


def test_failed_requests_count_as_wrong():
    reports = load_reports()[:2]
    results = score(reports, [None, None])
    assert results["failed_requests"] == 2
    assert results["priority_accuracy"] == 0


def test_full_evaluation_runs_on_the_rules():
    reports = load_reports()
    results = score(reports, [structure_with_rules(r["report"]) for r in reports])
    assert 0 <= results["priority_accuracy"] <= 1
