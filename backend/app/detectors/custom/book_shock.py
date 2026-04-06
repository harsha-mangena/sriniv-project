"""Book Shock vs Execution Divergence (BSED) detector.

1. book_pressure_direction:
   bid_pressure = sum(new_bid_volume) - sum(canceled_bid_volume)
   ask_pressure = sum(new_ask_volume) - sum(canceled_ask_volume)
   pressure_signal = bid_pressure - ask_pressure

2. execution_direction:
   net_execution = buy_volume - sell_volume

3. BSED = |pressure_signal_normalized - execution_direction_normalized|

When pressure_signal is strong but execution goes opposite → suspicious.
"""

import math
from typing import Dict, Any, Optional, List

from app.detectors.base import BaseDetector, DetectionResult
from app.features.order_book import OrderBook


class BookShockDivergenceDetector(BaseDetector):
    """
    Book Shock vs Execution Divergence detector.

    Identifies manipulation where order book pressure (visible intent) diverges
    from actual execution (real behavior). When someone stacks orders to create
    apparent buy/sell pressure but actually trades the opposite direction.
    """

    def __init__(self, threshold: float = 0.5, min_volume: float = 0.1):
        self._threshold = threshold
        self._min_volume = min_volume
        # Historical pressure for normalization
        self._pressure_history: List[float] = []
        self._execution_history: List[float] = []
        self._max_history = 200

    @property
    def name(self) -> str:
        return "book_shock_divergence"

    @property
    def category(self) -> str:
        return "custom"

    @property
    def description(self) -> str:
        return "Book Shock vs Execution Divergence detecting intent vs outcome mismatches"

    def detect(self, features: Dict[str, Any], **kwargs) -> Optional[DetectionResult]:
        """Compute BSED and flag divergence."""
        order_book: Optional[OrderBook] = kwargs.get("order_book")
        recent_trades: List[Dict] = kwargs.get("recent_trades", [])

        if not order_book:
            return None

        # Step 1: Compute book pressure direction
        stats = order_book.stats
        # Using imbalance as proxy for net book pressure
        bid_vol = features.get("bid_volume", 0)
        ask_vol = features.get("ask_volume", 0)
        canceled_bid_estimate = stats.get("total_canceled_volume", 0) * 0.5
        canceled_ask_estimate = stats.get("total_canceled_volume", 0) * 0.5

        # Use bid/ask imbalance as primary signal
        bid_pressure = bid_vol - canceled_bid_estimate
        ask_pressure = ask_vol - canceled_ask_estimate
        pressure_signal = bid_pressure - ask_pressure  # positive = buy pressure

        self._pressure_history.append(pressure_signal)
        if len(self._pressure_history) > self._max_history:
            self._pressure_history = self._pressure_history[-self._max_history:]

        # Step 2: Compute execution direction
        buy_volume = sum(
            float(t.get("quantity", 0)) for t in recent_trades if t.get("side") == "buy"
        )
        sell_volume = sum(
            float(t.get("quantity", 0)) for t in recent_trades if t.get("side") == "sell"
        )
        net_execution = buy_volume - sell_volume  # positive = net buying

        self._execution_history.append(net_execution)
        if len(self._execution_history) > self._max_history:
            self._execution_history = self._execution_history[-self._max_history:]

        # Step 3: Normalize and compute divergence
        pressure_std = self._std(self._pressure_history) or 1.0
        execution_std = self._std(self._execution_history) or 1.0

        pressure_norm = pressure_signal / pressure_std if pressure_std > 0 else 0.0
        execution_norm = net_execution / execution_std if execution_std > 0 else 0.0

        # Clamp to [-1, 1] range
        pressure_norm = max(-1.0, min(1.0, pressure_norm / 3.0))
        execution_norm = max(-1.0, min(1.0, execution_norm / 3.0))

        bsed = abs(pressure_norm - execution_norm)

        # Only flag when there's meaningful activity
        total_volume = buy_volume + sell_volume
        if total_volume < self._min_volume:
            return None

        if bsed < self._threshold:
            return None

        score = min(1.0, bsed)

        # Determine the nature of divergence
        if pressure_norm > 0 and execution_norm < 0:
            divergence_desc = "Buy pressure in book but net selling"
        elif pressure_norm < 0 and execution_norm > 0:
            divergence_desc = "Sell pressure in book but net buying"
        else:
            divergence_desc = f"Book-execution divergence (pressure={pressure_norm:.2f}, execution={execution_norm:.2f})"

        contributing = [
            f"pressure_signal={pressure_norm:.3f}",
            f"execution_direction={execution_norm:.3f}",
            f"bsed={bsed:.3f}",
        ]

        return DetectionResult(
            event_type="spoofing",
            score=score,
            explanation=f"Book Shock Divergence: {bsed:.3f}. {divergence_desc}. "
                        f"Order book intent diverges from actual execution pattern.",
            raw_features={
                "bsed": bsed,
                "pressure_signal": pressure_signal,
                "pressure_normalized": pressure_norm,
                "net_execution": net_execution,
                "execution_normalized": execution_norm,
                "buy_volume": buy_volume,
                "sell_volume": sell_volume,
            },
            detector_name=self.name,
            detector_category=self.category,
            contributing_factors=contributing,
            confidence=min(1.0, score * 1.1),
        )

    @staticmethod
    def _std(values: List[float]) -> float:
        """Compute standard deviation."""
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return math.sqrt(variance)
