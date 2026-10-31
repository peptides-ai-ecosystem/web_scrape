"""Peek: what would a core sync write for one reference page (AWD-17).

Scrapes ONE page in memory (no shared CSV, no database) and runs the same mapper
chain the core sync uses, so the admin sees exactly the values a sync would
write. Nothing is stored here: the platform compares the payload with its own
peptide row and writes only the fields an admin picks (XR-8: the platform owns
those tables).

``research_stage`` is pep-pedia's maturity label. It is returned next to the
columns but is not one of them: it is never a legal or regulatory status.

``evidence`` (AID-4, additive) is the page's own wording for the sections the
columns do not carry: research protocols (goal, route, dose, frequency), the
quick guide, what to expect, reconstitution steps, quality indicators,
interactions and indications, one entry per method tab. Peptide research
(peptide-microservice) cites it as a reference-site source; nothing is mapped
or written from it here.
"""

from __future__ import annotations

from typing import Any

from app.core.models import PeptideData, ScrapeMode
from app.infrastructure.csv_storage import peptide_to_row
from app.repositories.peptide import is_empty_value
from app.services.sync.db_import_orchestrator import DbImportOrchestrator
from app.services.sync.method_resolution import METHOD_KEYWORD_MAP, resolve_method

#: The canonical method names the platform seeds; the peek has no database, so
#: a page's Method is resolved against these.
KNOWN_METHODS = frozenset(METHOD_KEYWORD_MAP.values())


def scrape_reference_page(url: str, page_load_timeout: float | None = None) -> tuple[list[PeptideData], list[dict]]:
    """One blocking browser read (core fields only). Returns ``(results, errors)``.

    ``page_load_timeout`` caps the driver's page load so a hung page cannot keep Chrome for
    Selenium's 300 s default.
    """
    from app.scrapers.pep_pedia.page_scraper import PageScraper

    # "eager": the extractors wait for their own elements, so do not also block on the load
    # event (third-party scripts/fonts can hold it past the whole peek budget on a small box).
    return PageScraper(
        scrape_mode=ScrapeMode.CORE_ONLY, page_load_timeout=page_load_timeout, page_load_strategy="eager"
    ).scrape(url)


#: Caps so one long page cannot crowd out the rest of a research prompt.
_TEXT_CAP = 400
_LIST_CAP = 6


def _cap(value: Any) -> str:
    return " ".join(str(value or "").split())[:_TEXT_CAP]


def _numbered(row: dict[str, Any], prefix: str) -> list[str]:
    values = [_cap(row.get(f"{prefix}{i}")) for i in range(1, 6)]
    return [v for v in values if v][:_LIST_CAP]


def page_evidence(row: dict[str, Any], payload: dict[str, Any], orchestrator: DbImportOrchestrator) -> dict[str, Any]:
    """The page's own text for one method tab, for research to cite (AID-4). Pure."""
    protocols = []
    for i in range(1, 6):
        goal = _cap(row.get(f"research_protocols_goal_{i}"))
        if not goal:
            continue
        protocols.append(
            {
                "goal": goal,
                "route": _cap(row.get(f"research_protocols_route_{i}") or row.get("route")),
                "dose": _cap(row.get(f"research_protocols_dose_{i}")),
                "frequency": _cap(row.get(f"research_protocols_frequency_{i}")),
            }
        )
    quick_guide = {
        key[len("quick_guide_") :]: _cap(value)
        for key, value in row.items()
        if isinstance(key, str) and key.startswith("quick_guide_") and _cap(value)
    }
    protocol_mapper = orchestrator.protocol_mapper
    steps = [_cap(s.get("description")) for s in protocol_mapper.reconst_mapper.map(row)]
    quality = [
        {"title": _cap(q.get("indicator_title")), "description": _cap(q.get("indicator_description"))}
        for q in protocol_mapper.quality_mapper.map(row)
    ]
    relations = payload["relations"]
    return {
        "method": _cap(row.get("Method")),
        "typical_dose": _cap(row.get("typical_dose")),
        "protocols": protocols[:_LIST_CAP],
        "quick_guide": dict(list(quick_guide.items())[:12]),
        "what_to_expect": _numbered(row, "what_to_expect_"),
        "reconstitution_steps": [s for s in steps if s][:10],
        "quality_indicators": [q for q in quality if q["title"] or q["description"]][:_LIST_CAP],
        "interactions": [
            {
                "peptide": _cap(r.get("secondary_peptide_name")),
                "type": _cap(r.get("interaction_type")),
                "description": _cap(r.get("description")),
            }
            for r in relations["interactions"]
        ][:_LIST_CAP],
        "indications": [
            {
                "title": _cap(r.get("indication_title")),
                "effectiveness": _cap(r.get("effectiveness_tag")),
                "description": _cap(r.get("description")),
            }
            for r in relations["indications"]
        ][:8],
    }


def _names(items: list[dict[str, Any]], key: str) -> list[str]:
    return [str(item.get(key) or "").strip() for item in items if str(item.get(key) or "").strip()]


def build_peek(url: str, results: list[PeptideData]) -> dict[str, Any]:
    """The mapped payload for the scraped page. Pure: no network, no database."""
    orchestrator = DbImportOrchestrator()
    peptide: dict[str, Any] = {}
    benefits: list[str] = []
    side_effects: list[str] = []
    counts = {"protocols": 0, "dosages": 0, "schedules": 0, "references": 0, "interactions": 0, "indications": 0}
    methods: list[dict[str, Any]] = []
    stage: str | None = None
    warnings: list[str] = []
    evidence: list[dict[str, Any]] = []

    for data in results:
        row = peptide_to_row(data)
        payload = orchestrator.map_row(row)
        for key, value in payload["group_b"]["peptide"].items():
            # First non-empty value wins, as the sequential fill-nulls sync does.
            if is_empty_value(peptide.get(key)):
                peptide[key] = None if is_empty_value(value) else value
        for name in _names(payload["relations"]["benefits"], "benefit_name"):
            if name not in benefits:
                benefits.append(name)
        for name in _names(payload["relations"]["side_effects"], "side_effect_name"):
            if name not in side_effects:
                side_effects.append(name)
        counts["protocols"] += len(payload["protocols"])
        counts["dosages"] += len(payload["group_a"]["dosages"])
        counts["schedules"] += len(payload["group_a"]["schedules"])
        counts["references"] += len(payload["relations"]["references"])
        counts["interactions"] += len(payload["relations"]["interactions"])
        counts["indications"] += len(payload["relations"]["indications"])
        resolution = resolve_method(data.method, KNOWN_METHODS)
        methods.append({"label": data.method, "resolved": resolution.method, "reason": resolution.reason})
        stage = stage or orchestrator.peptide_mapper.extras(row)["research_stage"]
        evidence.append(page_evidence(row, payload, orchestrator))

    for entry in methods:
        if entry["resolved"] is None:
            warnings.append(f"Method '{entry['label']}': {entry['reason']}; its protocols would not be written.")

    return {
        "url": url,
        "name": peptide.get("name"),
        "slug": peptide.get("slug"),
        "research_stage": stage,
        "peptide": peptide,
        "benefits": benefits,
        "side_effects": side_effects,
        "children": counts,
        "methods": methods,
        "warnings": warnings,
        "evidence": evidence,
    }
