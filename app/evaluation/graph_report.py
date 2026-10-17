"""Console and JSON reporting for the graph evaluation.

Split out of graph_evaluator.py to keep that file under 400 lines.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.evaluation.graph_evaluator import GraphPeptideEvalResult


def print_graph_console(results: list[GraphPeptideEvalResult]) -> None:
    total_peptides = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total_peptides - passed

    print(f"\n{'=' * 60}")
    print("  GRAPH EVALUATION SUMMARY")
    print(f"{'=' * 60}")
    print(f"  Peptides evaluated : {total_peptides}")
    print(f"  Passed             : {passed}")
    print(f"  Failed             : {failed}")
    print(f"{'=' * 60}")

    for r in results:
        status_icon = "✓" if r.passed else "✗"
        print(f"\n  [{status_icon}] {r.peptide_name}  (method: {r.administration_method})")
        for check in r.checks:
            detail_str = f"  → {check.detail}" if check.detail else ""
            print(f"       {check.icon} {check.name:<28} exp={check.expected!r:20}  act={check.actual!r}{detail_str}")


def save_graph_json(results: list[GraphPeptideEvalResult], path: str) -> None:
    import json as _json

    def _serialise(r: GraphPeptideEvalResult) -> dict:
        return {
            "peptide_name": r.peptide_name,
            "slug": r.slug,
            "administration_method": r.administration_method,
            "passed": r.passed,
            "fail_count": r.fail_count,
            "pass_count": r.pass_count,
            "total_checks": r.total,
            "checks": [
                {
                    "name": c.name,
                    "status": c.status,
                    "expected": c.expected,
                    "actual": c.actual,
                    "detail": c.detail,
                }
                for c in r.checks
            ],
        }

    payload = [_serialise(r) for r in results]
    with open(path, "w", encoding="utf-8") as f:
        _json.dump(payload, f, indent=2, default=str)
    print(f"\n[GRAPH-EVAL] JSON report saved to: {path}")
