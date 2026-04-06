"""Rule-based layering detection.

Detects patterns indicating layering:
1. Multi-level stacking: Orders placed at multiple consecutive price levels
2. Synchronized cancellation: Multiple orders canceled within a short window
3. Opposite-side execution following layered orders
"""

from typing import Dict, Any, Optional, List
from collections import defaultdict

from app.detectors.base import BaseDetector, DetectionResult
from app.features.order_book import OrderBook, OrderRecord


class LayeringRuleDetector(BaseDetector):
    """
    Rule-based layering detector.

    Layering involves placing multiple orders at different price levels on one
    side of the book to create artificial depth, then canceling them after
    trading on the opposite side.
    """

    def __init__(
        self,
        min_levels: int = 3,
        sync_cancel_window_ms: float = 2000.0,
        depth_concentration_threshold: float = 0.6,
        cancel_sync_threshold: float = 0.5,
    ):
        self._min_levels = min_levels
        self._sync_cancel_window_ms = sync_cancel_window_ms
        self._depth_threshold = depth_concentration_threshold
        self._cancel_sync_threshold = cancel_sync_threshold

    @property
    def name(self) -> str:
        return "layering_rules"

    @property
    def category(self) -> str:
        return "rule"

    @property
    def description(self) -> str:
        return "Detects layering via multi-level order stacking and synchronized cancellations"

    def detect(self, features: Dict[str, Any], **kwargs) -> Optional[DetectionResult]:
        """Run layering detection rules."""
        order_book: Optional[OrderBook] = kwargs.get("order_book")

        scores = []
        factors = []
        explanations = []

        # Rule 1: High depth concentration (orders clustered at few levels)
        depth_conc = features.get("depth_concentration", 0)
        if depth_conc > self._depth_threshold:
            score = (depth_conc - self._depth_threshold) / (1.0 - self._depth_threshold)
            scores.append(score * 0.2)
            factors.append(f"depth_concentration={depth_conc:.2f}")
            explanations.append(f"High depth concentration ({depth_conc:.2f})")

        # Rule 2: Strong bid/ask imbalance (one-sided pressure)
        imbalance = features.get("bid_ask_imbalance", 0)
        abs_imbalance = abs(imbalance)
        if abs_imbalance > 0.4:
            score = min(1.0, (abs_imbalance - 0.4) / 0.6)
            pressure_side = "bid" if imbalance > 0 else "ask"
            scores.append(score * 0.2)
            factors.append(f"imbalance={imbalance:.2f} ({pressure_side} side)")
            explanations.append(f"Strong {pressure_side}-side book pressure ({abs_imbalance:.2f})")

        # Rule 3: Synchronized cancellations
        if order_book:
            sync_score, sync_info = self._check_synchronized_cancels(order_book)
            if sync_score > 0.3:
                scores.append(sync_score * 0.3)
                factors.append(f"sync_cancel_score={sync_score:.2f}")
                explanations.append(
                    f"Synchronized cancellations detected ({sync_info.get('cancel_clusters', 0)} clusters)"
                )

        # Rule 4: Multi-level stacking
        if order_book:
            stack_score = self._check_multi_level_stacking(order_book)
            if stack_score > 0.3:
                scores.append(stack_score * 0.3)
                factors.append(f"stacking_score={stack_score:.2f}")
                explanations.append("Multi-level order stacking pattern detected")

        if not scores:
            return None

        total_score = min(1.0, sum(scores))

        if total_score < 0.15:
            return None

        return DetectionResult(
            event_type="layering",
            score=total_score,
            explanation="; ".join(explanations),
            raw_features={
                "depth_concentration": depth_conc,
                "bid_ask_imbalance": imbalance,
                "total_score": total_score,
            },
            detector_name=self.name,
            detector_category=self.category,
            contributing_factors=factors,
            confidence=min(1.0, total_score * 1.1),
        )

    def _check_synchronized_cancels(self, order_book: OrderBook) -> tuple:
        """
        Check for synchronized cancellations - multiple orders canceled
        within a short time window.
        """
        recent = order_book.get_recent_orders(100)
        canceled = [o for o in recent if o.canceled_at is not None]

        if len(canceled) < self._min_levels:
            return 0.0, {}

        # Group cancels by time proximity
        cancel_clusters = []
        current_cluster = [canceled[0]]

        for i in range(1, len(canceled)):
            if canceled[i].canceled_at and current_cluster[-1].canceled_at:
                time_diff = abs(
                    (canceled[i].canceled_at - current_cluster[-1].canceled_at).total_seconds() * 1000
                )
                if time_diff <= self._sync_cancel_window_ms:
                    current_cluster.append(canceled[i])
                else:
                    if len(current_cluster) >= self._min_levels:
                        cancel_clusters.append(current_cluster)
                    current_cluster = [canceled[i]]

        if len(current_cluster) >= self._min_levels:
            cancel_clusters.append(current_cluster)

        if not cancel_clusters:
            return 0.0, {}

        # Score based on largest cluster
        max_cluster_size = max(len(c) for c in cancel_clusters)
        score = min(1.0, max_cluster_size / (self._min_levels * 3))

        # Check if clustered cancels are on the same side
        for cluster in cancel_clusters:
            sides = set(o.side for o in cluster)
            if len(sides) == 1:  # All same side = more suspicious
                score = min(1.0, score * 1.3)

        return score, {"cancel_clusters": len(cancel_clusters), "max_cluster_size": max_cluster_size}

    def _check_multi_level_stacking(self, order_book: OrderBook) -> float:
        """Check for orders stacked at consecutive price levels."""
        active = order_book.get_active_orders()
        if len(active) < self._min_levels:
            return 0.0

        # Group by side and price
        bid_prices = sorted(set(o.price for o in active.values() if o.side == "bid"), reverse=True)
        ask_prices = sorted(set(o.price for o in active.values() if o.side == "ask"))

        bid_stack_score = self._score_consecutive_levels(bid_prices)
        ask_stack_score = self._score_consecutive_levels(ask_prices)

        return max(bid_stack_score, ask_stack_score)

    def _score_consecutive_levels(self, prices: List[float]) -> float:
        """Score how many consecutive price levels have orders."""
        if len(prices) < self._min_levels:
            return 0.0

        # Check for clusters of nearby prices
        max_consecutive = 1
        current_consecutive = 1

        for i in range(1, len(prices)):
            # Check if prices are "adjacent" (within 0.05% of each other)
            if prices[i - 1] > 0:
                relative_gap = abs(prices[i] - prices[i - 1]) / prices[i - 1]
                if relative_gap < 0.0005:  # 5 basis points
                    current_consecutive += 1
                    max_consecutive = max(max_consecutive, current_consecutive)
                else:
                    current_consecutive = 1

        if max_consecutive < self._min_levels:
            return 0.0

        return min(1.0, max_consecutive / (self._min_levels * 2))
