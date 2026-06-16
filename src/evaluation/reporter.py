"""
EvaluationReporter
==================
Renders PeptideEvalResult objects to the console (human-readable) and
optionally writes a JSON file.
"""
import json
from typing import Any, List, Optional
from src.evaluation.evaluation_engine import CheckResult, PeptideEvalResult


class EvaluationReporter:
    """Pretty-prints evaluation results and optionally saves a JSON report."""

    # ANSI colours (fall back gracefully on non-TTY terminals)
    _GREEN  = "\033[92m"
    _RED    = "\033[91m"
    _YELLOW = "\033[93m"
    _GREY   = "\033[90m"
    _BOLD   = "\033[1m"
    _RESET  = "\033[0m"

    def print_console(self, results: List[PeptideEvalResult]) -> None:
        """Print all results to stdout."""
        for res in results:
            self._print_peptide(res)

        self._print_summary(results)

    def save_json(self, results: List[PeptideEvalResult], path: str) -> None:
        """Serialize results to a JSON file."""
        data = [self._peptide_to_dict(r) for r in results]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        print(f"\n[EVAL] JSON report saved → {path}")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _colour(self, text: str, colour: str) -> str:
        return f"{colour}{text}{self._RESET}"

    def _status_colour(self, status: str) -> str:
        return {
            "PASS": self._GREEN,
            "FAIL": self._RED,
            "WARN": self._YELLOW,
            "SKIP": self._GREY,
        }.get(status, "")

    def _print_peptide(self, res: PeptideEvalResult) -> None:
        bar = "━" * 50
        header_colour = self._GREEN if res.passed else self._RED
        verdict = "✓ ALL PASSED" if res.passed else f"✗ {res.fail_count} FAILED"

        print(f"\n{self._BOLD}{bar}{self._RESET}")
        print(
            f" {self._colour(self._BOLD + res.peptide_name + self._RESET, header_colour)}"
            f"  {self._colour(verdict, header_colour)}"
            f"  ({res.pass_count}/{res.total} checks)"
        )
        print(f"{self._BOLD}{bar}{self._RESET}")

        for chk in res.checks:
            colour = self._status_colour(chk.status)
            icon   = self._colour(chk.icon, colour)
            name   = f"{chk.name:<30}"
            val    = ""
            if chk.status == "PASS" and chk.actual is not None:
                val = self._colour(f"actual={chk.actual}", self._GREY)
            elif chk.status in ("FAIL", "WARN"):
                val = self._colour(
                    f"expected={chk.expected}  actual={chk.actual}", colour
                )
                if chk.detail:
                    val += f"\n      {self._colour('→ ' + chk.detail, colour)}"
            elif chk.status == "SKIP":
                val = self._colour(chk.detail or "", self._GREY)
            print(f"  {icon} {name} {val}")

    def _print_summary(self, results: List[PeptideEvalResult]) -> None:
        total     = len(results)
        all_pass  = sum(1 for r in results if r.passed)
        has_fail  = total - all_pass

        bar = "━" * 50
        print(f"\n{self._BOLD}{bar}{self._RESET}")
        print(f" {self._BOLD}EVALUATION SUMMARY{self._RESET}")
        print(f"{self._BOLD}{bar}{self._RESET}")
        print(f"  Peptides evaluated : {total}")
        print(f"  Fully passed       : {self._colour(str(all_pass), self._GREEN)}")
        print(f"  Had failures       : {self._colour(str(has_fail), self._RED if has_fail else self._GREEN)}")
        if has_fail:
            failed_names = [r.peptide_name for r in results if not r.passed]
            print(f"  Failed peptides    : {', '.join(failed_names)}")
        print(f"{self._BOLD}{bar}{self._RESET}\n")

    @staticmethod
    def _check_to_dict(chk: CheckResult) -> dict:
        return {
            "name": chk.name,
            "status": chk.status,
            "expected": chk.expected,
            "actual": chk.actual,
            "detail": chk.detail,
        }

    def _peptide_to_dict(self, res: PeptideEvalResult) -> dict:
        return {
            "peptide_name": res.peptide_name,
            "slug": res.slug,
            "passed": res.passed,
            "pass_count": res.pass_count,
            "fail_count": res.fail_count,
            "total_checks": res.total,
            "checks": [self._check_to_dict(c) for c in res.checks],
        }
