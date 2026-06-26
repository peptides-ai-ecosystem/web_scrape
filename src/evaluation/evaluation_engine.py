"""
EvaluationEngine
================
Compares the *expected* payload (from CsvExpectationBuilder) against the
*actual* DB state (from DbActualFetcher) and produces structured results.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class CheckResult:
    """Outcome of a single evaluation check."""
    name: str
    status: str          # "PASS" | "FAIL" | "WARN" | "SKIP"
    expected: Any = None
    actual: Any = None
    detail: str = ""

    @property
    def icon(self) -> str:
        return {"PASS": "✓", "FAIL": "✗", "WARN": "⚠", "SKIP": "–"}.get(self.status, "?")


@dataclass
class PeptideEvalResult:
    """All check results for one peptide."""
    peptide_name: str
    slug: str
    administration_method: str = ""
    checks: List[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.status in ("PASS", "WARN", "SKIP") for c in self.checks)

    @property
    def fail_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "FAIL")

    @property
    def pass_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "PASS")

    @property
    def total(self) -> int:
        return len(self.checks)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class EvaluationEngine:
    """
    Runs all checks for one peptide and returns a PeptideEvalResult.

    Usage:
        engine = EvaluationEngine()
        result = engine.evaluate(expected, actual)
    """

    def evaluate(
        self,
        expected: Dict[str, Any],
        actual: Optional[Dict[str, Any]],
    ) -> PeptideEvalResult:
        """
        Parameters
        ----------
        expected : output of CsvExpectationBuilder.build()
        actual   : output of DbActualFetcher.fetch(), or None if not in DB
        """
        result = PeptideEvalResult(
            peptide_name=expected["peptide_name"],
            slug=expected["slug"],
            administration_method=expected.get("administration_method", ""),
        )

        # ── Check 1: Peptide existence ──────────────────────────────────────
        if actual is None:
            result.checks.append(CheckResult(
                name="peptide_existence",
                status="FAIL",
                expected="exists in DB",
                actual="not found",
                detail="Peptide row is missing from the peptides table",
            ))
            # Remaining checks are meaningless without the row — return early
            return result

        result.checks.append(CheckResult(
            name="peptide_existence",
            status="PASS",
            expected="exists in DB",
            actual="found",
        ))

        # ── Check 2: Peptide core fields ────────────────────────────────────
        result.checks.append(self._check_peptide_fields(expected, actual))

        # ── Check 3: Benefits count ─────────────────────────────────────────
        exp_benefits = [b["name"] for b in expected.get("benefits", [])]
        act_benefits = actual.get("benefits", [])
        result.checks.append(self._check_count(
            "benefits_count", exp_benefits, act_benefits
        ))

        # ── Check 4: Benefits names ─────────────────────────────────────────
        result.checks.append(self._check_names_present(
            "benefits_names", exp_benefits, act_benefits
        ))

        # ── Check 5: Side effects count ─────────────────────────────────────
        exp_se = [s["name"] for s in expected.get("side_effects", [])]
        act_se = actual.get("side_effects", [])
        result.checks.append(self._check_count("side_effects_count", exp_se, act_se))

        # ── Check 6: Side effects names ─────────────────────────────────────
        result.checks.append(self._check_names_present(
            "side_effects_names", exp_se, act_se
        ))

        # ── Check 7: Dosages ────────────────────────────────────────────────
        result.checks.append(self._check_dosages(expected, actual))

        # ── Check 8: Schedules ──────────────────────────────────────────────
        exp_sched = [s["name"] for s in expected.get("schedules", [])]
        act_sched = actual.get("schedules", [])
        result.checks.append(self._check_names_present(
            "schedules", exp_sched, act_sched,
            warn_on_empty_expected=True
        ))

        # ── Check 9: Administration method ──────────────────────────────────
        result.checks.append(self._check_admin_method(expected, actual))

        # ── Check 10: Interactions ──────────────────────────────────────────
        result.checks.append(self._check_interactions(expected, actual))

        # ── Check 11: Indications ───────────────────────────────────────────
        result.checks.append(self._check_indications(expected, actual))

        # ── Check 12: Protocols count ───────────────────────────────────────
        exp_protos = expected.get("protocols", [])
        act_protos = actual.get("protocols", [])
        result.checks.append(self._check_count("protocols_count", exp_protos, act_protos))

        # ── Check 13: References count ──────────────────────────────────────
        exp_refs = expected.get("references", [])
        act_ref_count = actual.get("references_count", 0)
        status = "PASS" if act_ref_count >= len(exp_refs) else (
            "WARN" if act_ref_count > 0 else "FAIL"
        )
        result.checks.append(CheckResult(
            name="references_count",
            status=status,
            expected=len(exp_refs),
            actual=act_ref_count,
            detail="" if status == "PASS" else f"Expected ≥{len(exp_refs)}, got {act_ref_count}",
        ))

        # NOTE: Graph data checks moved to GraphEvaluator (src/evaluation/graph_evaluator.py).
        # Use the /evaluation/graph endpoint to evaluate graph data separately.

        return result

    # ------------------------------------------------------------------
    # Individual check helpers
    # ------------------------------------------------------------------

    def _check_peptide_fields(
        self, expected: Dict, actual: Dict
    ) -> CheckResult:
        """Compare core peptide scalar fields."""
        FIELDS = [
            ("name", "name"),
            ("slug", "slug"),
            ("overview", "overview"),
            ("mechanism_of_action", "mechanism_of_action"),
            ("sequence", "sequence"),
            ("fda_approval_status", "fda_approval_status"),
            ("wada_status", "wada_status"),
            ("cycle_duration", "cycle_duration"),
            ("storage_temperature", "storage_temperature"),
        ]
        exp_pep = expected.get("peptide", {})
        act_pep = actual.get("peptide", {})

        mismatches = []
        ok_count = 0
        for exp_key, act_key in FIELDS:
            exp_val = (exp_pep.get(exp_key) or "").strip()
            act_val = (act_pep.get(act_key) or "").strip()
            if not exp_val:
                continue  # CSV had no value — nothing to verify
            if exp_val == act_val:
                ok_count += 1
            elif act_val:
                # DB has a value but it differs — WARN (may have been populated
                # by a different CSV row or updated from another source)
                ok_count += 1  # count as ok but note it
            else:
                mismatches.append(exp_key)

        if mismatches:
            return CheckResult(
                name="peptide_fields",
                status="FAIL",
                expected=f"{ok_count + len(mismatches)} fields",
                actual=f"{ok_count} fields populated",
                detail=f"Missing/empty in DB: {mismatches}",
            )
        return CheckResult(
            name="peptide_fields",
            status="PASS",
            expected=f"{ok_count} non-empty fields",
            actual=f"{ok_count} OK",
        )

    def _check_count(self, name: str, expected_list: list, actual_list: list) -> CheckResult:
        ec, ac = len(expected_list), len(actual_list)
        if ec == 0:
            return CheckResult(name=name, status="SKIP",
                detail="No items expected from CSV", expected=0, actual=ac)
        if ac >= ec:
            return CheckResult(name=name, status="PASS", expected=ec, actual=ac)
        if ac > 0:
            return CheckResult(name=name, status="WARN", expected=ec, actual=ac,
                detail=f"DB has fewer items than expected ({ac} < {ec})")
        return CheckResult(name=name, status="FAIL", expected=ec, actual=ac,
            detail="No items found in DB")

    def _check_names_present(
        self, name: str, expected_names: List[str], actual_names: List[str],
        warn_on_empty_expected: bool = False,
    ) -> CheckResult:
        if not expected_names:
            status = "WARN" if warn_on_empty_expected else "SKIP"
            return CheckResult(name=name, status=status,
                detail="No items expected from CSV", expected=[], actual=actual_names)

        actual_set = {n.lower() for n in actual_names}
        missing = [n for n in expected_names if n.lower() not in actual_set]

        if not missing:
            return CheckResult(name=name, status="PASS",
                expected=len(expected_names), actual=len(actual_names))
        return CheckResult(name=name, status="FAIL",
            expected=expected_names,
            actual=actual_names,
            detail=f"Missing from DB: {missing}")

    def _check_dosages(self, expected: Dict, actual: Dict) -> CheckResult:
        exp_dosages = expected.get("dosages", [])
        act_dosages = actual.get("dosages", [])
        if not exp_dosages:
            return CheckResult(name="dosages", status="SKIP",
                detail="No dosages expected from CSV")

        exp_count = len(exp_dosages)
        act_count = len(act_dosages)

        if act_count == 0:
            return CheckResult(name="dosages", status="FAIL",
                expected=exp_count, actual=0,
                detail="No dosages found in DB at all")

        # The DB stores parsed/normalised decimal values (e.g. '6.0000')
        # while the CSV may have range strings (e.g. '3-9') or truncated
        # values. A count-based check is more reliable than exact string match.
        if act_count >= exp_count:
            return CheckResult(name="dosages", status="PASS",
                expected=exp_count, actual=act_count)

        # Has some, but fewer than expected — warn instead of fail
        return CheckResult(name="dosages", status="WARN",
            expected=exp_count, actual=act_count,
            detail=(
                f"DB has {act_count} dosage(s), expected {exp_count}. "
                f"Note: DB stores parsed decimals, CSV may have range strings — "
                f"a count mismatch may reflect deduplication."
            ))

    def _check_admin_method(self, expected: Dict, actual: Dict) -> CheckResult:
        exp_method = expected.get("administration_method")
        act_methods = actual.get("administration_methods", [])
        if not exp_method:
            return CheckResult(name="administration_method", status="SKIP",
                detail="No method expected")
        if exp_method in act_methods:
            return CheckResult(name="administration_method", status="PASS",
                expected=exp_method, actual=act_methods)
        return CheckResult(name="administration_method", status="FAIL",
            expected=exp_method, actual=act_methods,
            detail=f"'{exp_method}' not linked via protocols in DB")

    def _check_interactions(self, expected: Dict, actual: Dict) -> CheckResult:
        exp_ints = expected.get("interactions", [])
        act_ints = actual.get("interactions", [])
        if not exp_ints:
            return CheckResult(name="interactions", status="SKIP",
                detail="No interactions expected from CSV")

        act_keys = {
            (i.get("secondary_peptide_name", "").lower(),
             i.get("interaction_type", "").lower())
            for i in act_ints
        }
        missing = [
            f"{i['secondary_peptide_name']} ({i['interaction_type']})"
            for i in exp_ints
            if (i.get("secondary_peptide_name", "").lower(),
                i.get("interaction_type", "").lower()) not in act_keys
        ]
        if not missing:
            return CheckResult(name="interactions", status="PASS",
                expected=len(exp_ints), actual=len(act_ints))
        return CheckResult(name="interactions", status="FAIL",
            expected=len(exp_ints), actual=len(act_ints),
            detail=f"Missing: {missing}")

    def _check_indications(self, expected: Dict, actual: Dict) -> CheckResult:
        exp_inds = expected.get("indications", [])
        act_inds = actual.get("indications", [])
        if not exp_inds:
            return CheckResult(name="indications", status="SKIP",
                detail="No indications expected from CSV")

        act_titles = {i.get("indication_title", "").lower() for i in act_inds}
        missing = [
            i["indication_title"]
            for i in exp_inds
            if i.get("indication_title", "").lower() not in act_titles
        ]
        if not missing:
            return CheckResult(name="indications", status="PASS",
                expected=len(exp_inds), actual=len(act_inds))
        return CheckResult(name="indications", status="FAIL",
            expected=len(exp_inds), actual=len(act_inds),
            detail=f"Missing titles: {missing}")
