"""Layering Pressure Index (LPI) - detects layered order patterns.

For each side (bid/ask):
  1. Detect clusters: group orders within N adjacent price levels
  2. cluster_density = number_of_orders / price_level_span
  3. persistence = mean_lifetime of cluster orders
  4. sync_cancel_score = proportion canceled within T seconds
  5. opposite_execution = trades on opposite side within T seconds

LPI = cluster_density * (1/persistence) * sync_cancel_score * opposite_execution_volume
"""

from typing import Dict, Any, Optional, List, Tuple
from collections import defaultdict

from app.detectors.base import BaseDetector, DetectionResult
from app.features.order_book import OrderBook, OrderRecord


class LayeringPressureDetector(BaseDetector):
    """
    Layering Pressure Index detector.

    Identifies layering by detecting clusters of orders at adjacent price
    levels that are quickly canceled after opposite-side executions.
    """

    def __init__(
        self,
        price_cluster_pct: float = 0.001,  # 0.1% price proximity for clustering
        sync_window_ms: float = 2000.0,
        threshold: float = 0.4,
        min_cluster_size: int = 3,
    ):
        self._price_cluster_pct = price_cluster_pct
        self._sync_window_ms = sync_window_ms
        self._threshold = threshold
        self._min_cluster_size = min_cluster_size

    @property
    def name(self) -> str:
        return "layering_pressure"

    @property
    def category(self) -> str:
        return "custom"

    @property
    def description(self) -> str:
        return "Layering Pressure Index detecting multi-level order stacking patterns"

    def detect(self, features: Dict[str, Any], **kwargs) -> Optional[DetectionResult]:
        """Compute LPI and flag if above threshold."""
        order_book: Optional[OrderBook] = kwargs.get("order_book")
        recent_trades: List[Dict] = kwargs.get("recent_trades", [])

        if not order_book:
            return None

        recent_orders = order_book.get_recent_orders(200)
        if len(recent_orders) < self._min_cluster_size:
            return None

        # Analyze both sides
        bid_lpi = self._compute_side_lpi(recent_orders, "bid", recent_trades)
        ask_lpi = self._compute_side_lpi(recent_orders, "ask", recent_trades)

        max_lpi = max(bid_lpi, ask_lpi)
        pressure_side = "bid" if bid_lpi > ask_lpi else "ask"

        if max_lpi < self._threshold:
            return None

        score = min(1.0, max_lpi)

        contributing = []
        if bid_lpi > self._threshold:
            contributing.append(f"bid_lpi={bid_lpi:.3f}")
        if ask_lpi > self._threshold:
            contributing.append(f"ask_lpi={ask_lpi:.3f}")

        return DetectionResult(
            event_type="layering",
            score=score,
            explanation=f"Layering Pressure Index: {max_lpi:.3f} on {pressure_side} side. "
                        f"Detected clustered orders at adjacent price levels with "
                        f"synchronized cancellations.",
            raw_features={
                "bid_lpi": bid_lpi,
                "ask_lpi": ask_lpi,
                "max_lpi": max_lpi,
                "pressure_side": pressure_side,
            },
            detector_name=self.name,
            detector_category=self.category,
            contributing_factors=contributing,
            confidence=min(1.0, score * 1.1),
        )

    def _compute_side_lpi(
        self,
        orders: List[OrderRecord],
        side: str,
        recent_trades: List[Dict],
    ) -> float:
        """Compute LPI for a specific side of the book."""
        side_orders = [o for o in orders if o.side == side]
        if len(side_orders) < self._min_cluster_size:
            return 0.0

        # Step 1: Detect clusters by price proximity
        clusters = self._find_price_clusters(side_orders)
        if not clusters:
            return 0.0

        max_cluster_lpi = 0.0
        for cluster in clusters:
            if len(cluster) < self._min_cluster_size:
                continue

            # Step 2: Cluster density
            prices = [o.price for o in cluster]
            price_span = max(prices) - min(prices) if len(prices) > 1 else 1.0
            avg_price = sum(prices) / len(prices)
            # Normalize span as percentage
            price_span_pct = (price_span / avg_price) if avg_price > 0 else 1.0
            cluster_density = len(cluster) / max(price_span_pct * 10000, 1.0)
            cluster_density = min(1.0, cluster_density / 10.0)

            # Step 3: Persistence (inverse of lifetime = impersistence)
            lifetimes = [o.lifetime_ms for o in cluster if o.lifetime_ms is not None and o.lifetime_ms > 0]
            if lifetimes:
                avg_persistence_s = (sum(lifetimes) / len(lifetimes)) / 1000.0
                impersistence = min(1.0, 1.0 / max(avg_persistence_s, 0.1))
            else:
                impersistence = 0.0

            # Step 4: Synchronized cancel score
            canceled = [o for o in cluster if o.canceled_at is not None]
            sync_cancel_score = len(canceled) / len(cluster)

            # Check synchronization
            if len(canceled) > 1:
                cancel_times = sorted([o.canceled_at for o in canceled if o.canceled_at])
                if len(cancel_times) > 1:
                    max_spread = (cancel_times[-1] - cancel_times[0]).total_seconds() * 1000
                    if max_spread < self._sync_window_ms:
                        sync_cancel_score = min(1.0, sync_cancel_score * 1.5)

            # Step 5: Opposite-side execution volume
            opposite_side = "sell" if side == "bid" else "buy"
            opposite_vol = sum(
                float(t.get("quantity", 0))
                for t in recent_trades
                if t.get("side") == opposite_side
            )
            total_trade_vol = sum(float(t.get("quantity", 0)) for t in recent_trades) or 1.0
            opposite_exec = opposite_vol / total_trade_vol

            # Compute cluster LPI
            cluster_lpi = cluster_density * impersistence * sync_cancel_score * opposite_exec
            max_cluster_lpi = max(max_cluster_lpi, cluster_lpi)

        return max_cluster_lpi

    def _find_price_clusters(self, orders: List[OrderRecord]) -> List[List[OrderRecord]]:
        """Group orders into clusters based on price proximity."""
        if not orders:
            return []

        sorted_orders = sorted(orders, key=lambda o: o.price)
        clusters = []
        current_cluster = [sorted_orders[0]]

        for i in range(1, len(sorted_orders)):
            prev_price = sorted_orders[i - 1].price
            curr_price = sorted_orders[i].price

            if prev_price > 0:
                relative_gap = abs(curr_price - prev_price) / prev_price
                if relative_gap <= self._price_cluster_pct:
                    current_cluster.append(sorted_orders[i])
                else:
                    clusters.append(current_cluster)
                    current_cluster = [sorted_orders[i]]
            else:
                current_cluster.append(sorted_orders[i])

        clusters.append(current_cluster)
        return [c for c in clusters if len(c) >= self._min_cluster_size]
