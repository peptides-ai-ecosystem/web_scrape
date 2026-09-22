"""Confidence scoring and delta review for scraped competitor prices (#288).

A scraped price is a **guess about somebody else's website**. Layouts change
without warning and a selector that used to read the price can start reading
the shipping estimate, the strikethrough RRP, or nothing. So two separate
safeguards live here.

**Confidence** answers "how much of what we were told to look for did we
actually find, and did we find it where we expected?" It is computed purely
from :class:`~src.core.vendor_models.FieldMatch` records — which selector hit,
and how far down the fallback list it was. It is explicitly *not* a function
of whether the run completed, whether the HTTP status was 200, or how many
pages we got through: all of those can be perfect while the extraction is
junk.

**Delta review** answers "is this reading believable given what we last
accepted?" A large price move is exactly what a broken selector looks like, so
a move beyond the threshold is flagged for a human and, critically, **does not
replace the last accepted value** — the previously good price stays the
current one until someone confirms the new one.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Optional

from src.core.vendor_models import (
    ConfidenceBreakdown,
    ExtractedFields,
    ReviewReason,
    ReviewStatus,
    VendorObservation,
    VendorTarget,
)

logger = logging.getLogger(__name__)

#: What each field is worth. Price dominates because it is the thing we are
#: actually here for; a run that read the stock badge and the COA link but not
#: the price has learned almost nothing worth publishing.
FIELD_WEIGHTS: Dict[str, float] = {
    "price": 0.55,
    "stock": 0.20,
    "coa": 0.15,
    "product_name": 0.10,
}

#: A field found only via a fallback selector counts for less: "we found a
#: number somewhere on the page" is a weaker claim than "we found the element
#: we were told was the price". Index 0 keeps full weight, index 1 keeps 75%,
#: index 2+ keeps 50%.
_FALLBACK_MULTIPLIERS = (1.0, 0.75, 0.5)


def _fallback_multiplier(selector_index: int) -> float:
    if selector_index < 0:
        return 0.0
    if selector_index < len(_FALLBACK_MULTIPLIERS):
        return _FALLBACK_MULTIPLIERS[selector_index]
    return _FALLBACK_MULTIPLIERS[-1]


def score_confidence(fields: ExtractedFields, target: VendorTarget) -> ConfidenceBreakdown:
    """Score an extraction on what it matched.

    Only fields the target actually asked for are in the denominator: a vendor
    whose config declares no COA selector is not penalised for having no COA,
    because we never looked. A vendor that *does* declare one and returned
    nothing is penalised, because that is a real miss.
    """
    configured = {
        "price": bool(target.selectors.price),
        "stock": bool(target.selectors.stock),
        "coa": bool(target.selectors.coa),
        "product_name": bool(target.selectors.product_name),
    }

    total_weight = sum(FIELD_WEIGHTS[f] for f, on in configured.items() if on)
    breakdown = ConfidenceBreakdown(score=0.0)

    if total_weight <= 0:
        breakdown.notes.append(
            "target declares no selectors — nothing could be matched, confidence 0"
        )
        return breakdown

    earned = 0.0
    for field_name, is_configured in configured.items():
        if not is_configured:
            continue
        match = fields.matches.get(field_name)
        if match is None:
            breakdown.contributions[field_name] = 0.0
            breakdown.notes.append(f"{field_name}: no selector matched a usable value")
            continue
        contribution = FIELD_WEIGHTS[field_name] * _fallback_multiplier(match.selector_index)
        breakdown.contributions[field_name] = contribution
        earned += contribution
        if match.selector_index > 0:
            breakdown.notes.append(
                f"{field_name}: matched on fallback selector #{match.selector_index} "
                f"({match.selector!r}) — discounted"
            )

    breakdown.score = max(0.0, min(1.0, earned / total_weight))
    return breakdown


# ---------------------------------------------------------------------------
# Delta review
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReviewDecision:
    status: ReviewStatus
    reason: Optional[ReviewReason] = None
    note: Optional[str] = None

    @property
    def supersedes_previous(self) -> bool:
        """Whether this reading may become the current accepted value."""
        return self.status is ReviewStatus.ACCEPTED


class DeltaReviewer:
    """Decides whether an observation can stand on its own.

    Args:
        min_confidence: below this, always flag.
        delta_threshold: relative price move (0.25 == 25%) beyond which a
            reading is flagged instead of replacing the accepted value.
    """

    def __init__(self, min_confidence: float = 0.6, delta_threshold: float = 0.25):
        self._min_confidence = min_confidence
        self._delta_threshold = delta_threshold

    def assess(
        self,
        current: VendorObservation,
        previous: Optional[VendorObservation] = None,
    ) -> ReviewDecision:
        # 1. No price at all. Store the observation (it is evidence that the
        #    page changed) but never let it stand in for a price, and never
        #    write a placeholder. A missing price stays missing.
        if current.price is None:
            return ReviewDecision(
                ReviewStatus.FLAGGED,
                ReviewReason.NO_PRICE,
                "no plausible price found on the page",
            )

        # 2. We found something, but not where we expected it.
        if current.confidence < self._min_confidence:
            return ReviewDecision(
                ReviewStatus.FLAGGED,
                ReviewReason.LOW_CONFIDENCE,
                f"confidence {current.confidence:.2f} below threshold "
                f"{self._min_confidence:.2f}",
            )

        if previous is None or previous.price is None:
            # First good reading for this URL. Nothing to contradict it.
            return ReviewDecision(ReviewStatus.ACCEPTED)

        # 3. A currency change is never a price move — it is a different
        #    number entirely, and comparing them would be meaningless.
        if (
            current.currency
            and previous.currency
            and current.currency != previous.currency
        ):
            return ReviewDecision(
                ReviewStatus.FLAGGED,
                ReviewReason.CURRENCY_CHANGED,
                f"currency changed {previous.currency} -> {current.currency}",
            )

        # 4. The delta gate.
        previous_price: Decimal = previous.price
        if previous_price <= 0:
            return ReviewDecision(ReviewStatus.ACCEPTED)

        delta = abs(current.price - previous_price) / previous_price
        if float(delta) > self._delta_threshold:
            direction = "up" if current.price > previous_price else "down"
            return ReviewDecision(
                ReviewStatus.FLAGGED,
                ReviewReason.PRICE_DELTA,
                f"price moved {direction} {float(delta) * 100:.1f}% "
                f"({previous_price} -> {current.price}), above the "
                f"{self._delta_threshold * 100:.0f}% review threshold; "
                "previous accepted value retained",
            )

        return ReviewDecision(ReviewStatus.ACCEPTED)
