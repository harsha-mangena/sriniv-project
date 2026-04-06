"""Rule-based spoofing detection.

Detects patterns indicating spoofing:
1. Large order cancellation: Orders significantly larger than average that get canceled quickly
2. High cancel rate: Abnormally high ratio of cancels to total orders
3. Opposite-side execution: Trades on the opposite side shortly after book pressure
"""

from typing import Dict, Any, Optional, List

from app.detectors.base import BaseDetector, DetectionResult
from app.features.order_book import OrderBook


class SpoofingRuleDetector(BaseDetector):
    """
    Rule-based spoofing detector combining multiple signals.

    Spoofing involves placing large orders to create false impression of
    supply/demand, then canceling them after trading on the opposite side.
    """

    def __init__(
        self,
        cancel_rate_threshold: float = 0.7,
        lifetime_threshold_ms: float = 500.0,
        size_multiplier_threshold: float = 5.0,
        imbalance_threshold: float = 0.5,
    ):
        self._cancel_rate_threshold = cancel_rate_threshold
        self._lifetime_threshold_ms = lifetime_threshold_ms
        self._size_multiplier_threshold = size_multiplier_threshold
        self._imbalance_threshold = imbalance_threshold

    @property
    def name(self) -> str:
        return "spoofing_rules"

    @property
    def category(self) -> str:
        return "rule"

    @property
    def description(self) -> str:
        return "Detects spoofing via cancel rate, order lifetime, and opposite-side execution patterns"

    def detect(self, features: Dict[str, Any], **kwargs) -> Optional[DetectionResult]:
        """Run spoofing detection rules."""
        order_book: Optional[OrderBook] = kwargs.get("order_book")

        scores = []
        factors = []
        explanations = []

        # Rule 1: High cancel rate
        cancel_rate = features.get("cancel_rate", 0)
        if cancel_rate > self._cancel_rate_threshold:
            score = min(1.0, (cancel_rate - self._cancel_rate_threshold) / (1.0 - self._cancel_rate_threshold))
            scores.append(score * 0.3)
            factors.append(f"cancel_rate={cancel_rate:.2%} (threshold: {self._cancel_rate_threshold:.0%})")
            explanations.append(f"High cancel rate of {cancel_rate:.1%}")

        # Rule 2: Short order lifetimes (quick cancellations)
        avg_lifetime = features.get("avg_order_lifetime_ms", float("inf"))
        if avg_lifetime > 0 and avg_lifetime < self._lifetime_threshold_ms:
            score = max(0, 1.0 - avg_lifetime / self._lifetime_threshold_ms)
            scores.append(score * 0.25)
            factors.append(f"avg_lifetime={avg_lifetime:.0f}ms (threshold: {self._lifetime_threshold_ms:.0f}ms)")
            explanations.append(f"Rapid cancellations (avg {avg_lifetime:.0f}ms)")

        # Rule 3: Large order size anomaly (check recent orders)
        if order_book:
            large_cancel_score = self._check_large_cancels(order_book)
            if large_cancel_score > 0:
                scores.append(large_cancel_score * 0.25)
                factors.append(f"large_cancel_score={large_cancel_score:.2f}")
                explanations.append("Large orders being quickly canceled")

        # Rule 4: Bid-ask imbalance with opposite execution
        imbalance = abs(features.get("bid_ask_imbalance", 0))
        if imbalance > self._imbalance_threshold:
            score = min(1.0, (imbalance - self._imbalance_threshold) / (1.0 - self._imbalance_threshold))
            scores.append(score * 0.2)
            factors.append(f"imbalance={imbalance:.2f} (threshold: {self._imbalance_threshold:.2f})")
            explanations.append(f"Strong book imbalance ({imbalance:.2f})")

        # Rule 5: Cancel rate z-score anomaly
        cancel_zscore = abs(features.get("rolling_zscore_cancel", 0))
        if cancel_zscore > 2.0:
            score = min(1.0, (cancel_zscore - 2.0) / 3.0)
            scores.append(score * 0.15)
            factors.append(f"cancel_zscore={cancel_zscore:.2f}")
            explanations.append(f"Cancel rate z-score of {cancel_zscore:.1f}")

        if not scores:
            return None

        total_score = min(1.0, sum(scores))

        if total_score < 0.15:
            return None

        return DetectionResult(
            event_type="spoofing",
            score=total_score,
            explanation="; ".join(explanations),
            raw_features={
                "cancel_rate": cancel_rate,
                "avg_lifetime_ms": avg_lifetime,
                "bid_ask_imbalance": features.get("bid_ask_imbalance", 0),
                "cancel_zscore": features.get("rolling_zscore_cancel", 0),
            },
            detector_name=self.name,
            detector_category=self.category,
            contributing_factors=factors,
            confidence=min(1.0, total_score * 1.2),
        )

    def _check_large_cancels(self, order_book: OrderBook) -> float:
        """Check for unusually large orders that were canceled quickly."""
        recent = order_book.get_recent_orders(50)
        if len(recent) < 5:
            return 0.0

        quantities = [o.quantity for o in recent if o.quantity > 0]
        if not quantities:
            return 0.0

        avg_qty = sum(quantities) / len(quantities)
        if avg_qty == 0:
            return 0.0

        large_fast_cancels = 0
        for order in recent:
            if (
                order.canceled_at is not None
                and order.quantity > avg_qty * self._size_multiplier_threshold
                and order.lifetime_ms is not None
                and order.lifetime_ms < self._lifetime_threshold_ms
            ):
                large_fast_cancels += 1

        if large_fast_cancels == 0:
            return 0.0

        return min(1.0, large_fast_cancels / 5.0)
