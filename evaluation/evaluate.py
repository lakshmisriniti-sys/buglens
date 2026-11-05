"""Score BugLens tickets against the labelled reports in reports.jsonl.

Run from the project root:
    python -m evaluation.evaluate --engine rules
    python -m evaluation.evaluate --engine claude     (needs ANTHROPIC_API_KEY, makes 50 paid calls)
"""
import argparse
import json
from pathlib import Path

from ai import AIError, _ask_claude
from evaluation import metrics
from rules import structure_with_rules
from schemas import AITicket

HERE = Path(__file__).parent
ENGINES = {"rules": structure_with_rules, "claude": _ask_claude}


def load_reports(path: Path = HERE / "reports.jsonl") -> list[dict]:
    with open(path, encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def score(reports: list[dict], tickets: list[AITicket | None]) -> dict:
    """Score the tickets. A failed request (None) counts as wrong on every measure."""
    gold = [r["priority"] for r in reports]
    predicted = [t.priority if t else "failed" for t in tickets]

    correct = sum(g == p for g, p in zip(gold, predicted))
    env_scores = [
        metrics.environment_recall(r["environment"], t.environment if t else "")
        for r, t in zip(reports, tickets)
    ]
    env_scores = [s for s in env_scores if s is not None]
    area_hits = sum(
        bool(t) and metrics.area_hit(r["areas"], t.labels) for r, t in zip(reports, tickets)
    )
    injected = [(r, t) for r, t in zip(reports, tickets) if "injection" in r.get("tags", [])]
    resisted = sum(
        bool(t) and metrics.injection_resisted(r["priority"], t.priority, t.title, t.labels)
        for r, t in injected
    )

    return {
        "reports": len(reports),
        "failed_requests": sum(t is None for t in tickets),
        "priority_accuracy": correct / len(reports),
        "priority_accuracy_95ci": metrics.wilson_interval(correct, len(reports)),
        "priority_macro_f1": metrics.macro_f1(gold, predicted),
        "per_priority": metrics.per_class(gold, predicted),
        "confusion_matrix": metrics.confusion_matrix(gold, predicted),
        "environment_recall": sum(env_scores) / len(env_scores),
        "area_hit_rate": area_hits / len(reports),
        "injection_resisted": f"{resisted}/{len(injected)}",
    }


def print_summary(engine: str, results: dict) -> None:
    low, high = results["priority_accuracy_95ci"]
    print(f"Engine: {engine} ({results['reports']} reports, {results['failed_requests']} failed)")
    print(f"Priority accuracy:  {percent(results['priority_accuracy'])} (95% CI {percent(low)}-{percent(high)})")
    print(f"Priority macro F1:  {results['priority_macro_f1']:.3f}")
    print(f"Critical recall:    {percent(results['per_priority']['critical']['recall'])}")
    print(f"Environment recall: {percent(results['environment_recall'])}")
    print(f"Area hit rate:      {percent(results['area_hit_rate'])}")
    print(f"Injection resisted: {results['injection_resisted']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--engine", choices=ENGINES, default="rules")
    args = parser.parse_args()

    reports = load_reports()
    tickets = []
    for report in reports:
        try:
            tickets.append(ENGINES[args.engine](report["report"]))
        except AIError as error:
            print(f"Report {report['id']} failed: {error}")
            tickets.append(None)

    results = score(reports, tickets)
    print_summary(args.engine, results)

    details = [
        {"id": r["id"], "gold": r["priority"], "predicted": t.priority if t else None, "labels": t.labels if t else []}
        for r, t in zip(reports, tickets)
    ]
    output = HERE / "results" / f"{args.engine}.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps({"summary": results, "details": details}, indent=2), encoding="utf-8")
    print(f"Saved {output.relative_to(HERE.parent)}")


if __name__ == "__main__":
    main()
