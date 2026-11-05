import pytest

from rules import structure_with_rules


@pytest.mark.parametrize("report, priority", [
    ("i got charged twice for my order", "critical"),
    ("the login page is broken", "high"),
    ("the dashboard takes a while", "medium"),
    ("there is a typo on the about page", "low"),
])
def test_priority(report, priority):
    assert structure_with_rules(report).priority == priority


def test_environment_and_browser_label():
    ticket = structure_with_rules("the search is broken on chrome on windows")
    assert ticket.environment == "Chrome, Windows"
    assert "chrome" in ticket.labels


def test_intermittent_problems_are_named_in_the_title():
    assert structure_with_rules("login sometimes fails").title.startswith("Intermittent login")


def test_unknown_report_is_sent_for_triage():
    ticket = structure_with_rules("something feels strange today")
    assert ticket.labels == ["needs-triage"]
    assert ticket.priority == "medium"
    assert ticket.title


def test_very_long_report_keeps_fields_short():
    ticket = structure_with_rules("word " * 2000)
    assert len(ticket.title) <= 80
    assert len(ticket.actual) <= 200
