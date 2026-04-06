"""Liquidity Mirage Score (LMS) - detects deceptive liquidity patterns.

LMS = w1 * (displayed_depth / avg_depth)
    * w2 * (cancel_velocity / baseline_cancel_velocity)
    * w3 * (1 - execution_ratio)
    * w4 * (1 / avg_order_lifetime_seconds)
    * w5 * refill_frequency

High LMS indicates orders creating an illusion of liquidity that rapidly
disappears before execution.
"""

from typing import Dict, Any, Optional
from collections import defaultdict

from app.detectors.base import BaseDetector, DetectionResult
from app.features.order_book import OrderBook


class LiquidityMirageDetector(BaseDetector):
    """
    Detects deceptive liquidity by computing the Liquidity Mirage Score.

    Identifies cases where displayed order book depth is misleading:
    - High displayed depth relative to average
    - High cancel velocity
    - Low execution ratio (orders rarely fill)
    - Short order lifetimes
    - Frequent refills after cancellation
    """

    def __init__(
        self,
        w1: float = 0.25,
        w2: float = 0.25,
        w3: float = 0.20,
        w4: float = 0.15,
        w5: float = 0.15,
        threshold: float = 0.5,
        depth_ticks: int = 5,
    ):
        self._weights = [w1, w2, w3, w4, w5]
        self._threshold = threshold
        self._depth_ticks = depth_ticks
        # Running baselines
        self._avg_depth_history = []
        self._cancel_velocity_history = []
        self._max_history = 500
        # Track refills: size_bucket -> count of reappearances
        self._canceled_sizes: Dict[str, int] = defaultdict(int)

    @property
    def name(self) -> str:
        return "liquidity_mirage"

    @property
    def category(self) -> str:
        return "custom"

    @property
    def description(self) -> str:
        return "Liquidity Mirage Score detecting deceptive displayed depth"

    def detect(self, features: Dict[str, Any], **kwargs) -> Optional[DetectionResult]:
        """Compute LMS and flag if above threshold."""
        order_book: Optional[OrderBook] = kwargs.get("order_book")

        # Component 1: displayed_depth / avg_depth
        bid_vol = features.get("bid_volume", 0)
        ask_vol = features.get("ask_volume", 0)
        displayed_depth = bid_vol + ask_vol

        self._avg_depth_history.append(displayed_depth)
        if len(self._avg_depth_history) > self._max_history:
            self._avg_depth_history = self._avg_depth_history[-self._max_history:]

        avg_depth = sum(self._avg_depth_history) / len(self._avg_depth_history) if self._avg_depth_history else 1.0
        depth_ratio = displayed_depth / avg_depth if avg_depth > 0 else 0.0
        # Normalize: >2x average is suspicious
        c1 = min(1.0, max(0.0, (depth_ratio - 1.0) / 2.0))

        # Component 2: cancel_velocity / baseline
        total_cancels = features.get("total_cancels", 0)
        window_seconds = 60  # default window
        cancel_velocity = total_cancels / window_seconds if window_seconds > 0 else 0.0

        self._cancel_velocity_history.append(cancel_velocity)
        if len(self._cancel_velocity_history) > self._max_history:
            self._cancel_velocity_history = self._cancel_velocity_history[-self._max_history:]

        baseline_velocity = sum(self._cancel_velocity_history) / len(self._cancel_velocity_history)
        velocity_ratio = cancel_velocity / baseline_velocity if baseline_velocity > 0 else 0.0
        c2 = min(1.0, max(0.0, (velocity_ratio - 1.0) / 3.0))

        # Component 3: 1 - execution_ratio
        total_placed = features.get("total_orders", 0)
        total_trades = features.get("total_trades", 0)
        execution_ratio = total_trades / total_placed if total_placed > 0 else 0.0
        c3 = 1.0 - execution_ratio

        # Component 4: 1 / avg_order_lifetime_seconds
        avg_lifetime_ms = features.get("avg_order_lifetime_ms", 5000)
        avg_lifetime_s = avg_lifetime_ms / 1000.0 if avg_lifetime_ms > 0 else 5.0
        # Normalize: <1s is very suspicious
        c4 = min(1.0, max(0.0, 1.0 / max(avg_lifetime_s, 0.1) / 5.0))

        # Component 5: refill_frequency
        refill_freq = self._estimate_refill_frequency(order_book) if order_book else 0.0
        c5 = min(1.0, refill_freq)

        # Compute LMS
        w1, w2, w3, w4, w5 = self._weights
        lms = w1 * c1 + w2 * c2 + w3 * c3 + w4 * c4 + w5 * c5

        if lms < self._threshold:
            return None

        # Normalize score to 0-1
        score = min(1.0, lms / 1.0)

        contributing = []
        if c1 > 0.3:
            contributing.append(f"depth_ratio={depth_ratio:.2f} ({c1:.2f})")
        if c2 > 0.3:
            contributing.append(f"cancel_velocity_ratio={velocity_ratio:.2f} ({c2:.2f})")
        if c3 > 0.5:
            contributing.append(f"low_execution_ratio={execution_ratio:.2f} ({c3:.2f})")
        if c4 > 0.3:
            contributing.append(f"short_lifetime={avg_lifetime_ms:.0f}ms ({c4:.2f})")
        if c5 > 0.3:
            contributing.append(f"refill_frequency={refill_freq:.2f} ({c5:.2f})")

        return DetectionResult(
            event_type="spoofing",
            score=score,
            explanation=f"Liquidity Mirage Score: {lms:.3f}. "
                        f"Displayed depth appears deceptive with high cancel velocity "
                        f"and low execution ratio.",
            raw_features={
                "lms": lms,
                "depth_ratio": depth_ratio,
                "cancel_velocity_ratio": velocity_ratio,
                "execution_ratio": execution_ratio,
                "avg_lifetime_ms": avg_lifetime_ms,
                "refill_frequency": refill_freq,
                "components": [c1, c2, c3, c4, c5],
            },
            detector_name=self.name,
            detector_category=self.category,
            contributing_factors=contributing,
            confidence=min(1.0, score * 1.1),
        )

    def _estimate_refill_frequency(self, order_book: OrderBook) -> float:
        """
        Estimate how frequently canceled orders are "refilled" with similar-sized orders.

        Groups orders by size buckets and checks for repeat placements.
        """
        recent = order_book.get_recent_orders(100)
        if len(recent) < 10:
            return 0.0

        # Count cancels followed by similar-size placements
        size_buckets = defaultdict(list)
        for order in recent:
            bucket = round(order.quantity, 2)
            size_buckets[bucket].append(order)

        refill_count = 0
        total_cancels = 0
        for bucket, orders in size_buckets.items():
            canceled = [o for o in orders if o.canceled_at is not None]
            total_cancels += len(canceled)
            if len(canceled) > 1:
                # Multiple orders of same size = potential refill
                refill_count += len(canceled) - 1

        return refill_count / total_cancels if total_cancels > 0 else 0.0
