"""Rule-based wash trading detection.

Detects patterns indicating wash trading:
1. Trade loop detection: alternating buy/sell with symmetric sizes
2. Symmetric timing: regular intervals between trades
3. Volume recycling: high ratio of min(buy,sell) to total volume
"""

import math
from typing import Dict, Any, Optional, List
from collections import deque

from app.detectors.base import BaseDetector, DetectionResult
from app.ingestion.base import MarketEvent


class WashTradingRuleDetector(BaseDetector):
    """
    Rule-based wash trading detector.

    Wash trading involves simultaneously buying and selling the same asset
    to create misleading market activity. Key signals:
    - Alternating buy/sell pattern with similar sizes
    - Regular inter-trade timing
    - High volume recycling ratio
    """

    def __init__(
        self,
        size_tolerance: float = 0.05,
        timing_cv_threshold: float = 0.3,
        volume_recycling_threshold: float = 0.7,
        min_trades: int = 4,
    ):
        self._size_tolerance = size_tolerance
        self._timing_cv_threshold = timing_cv_threshold
        self._volume_recycling_threshold = volume_recycling_threshold
        self._min_trades = min_trades

    @property
    def name(self) -> str:
        return "wash_trading_rules"

    @property
    def category(self) -> str:
        return "rule"

    @property
    def description(self) -> str:
        return "Detects wash trading via trade loop symmetry, timing regularity, and volume recycling"

    def detect(self, features: Dict[str, Any], **kwargs) -> Optional[DetectionResult]:
        """Run wash trading detection rules."""
        recent_trades: List[Dict] = kwargs.get("recent_trades", [])

        if len(recent_trades) < self._min_trades:
            return None

        scores = []
        factors = []
        explanations = []

        # Rule 1: Alternating buy/sell pattern
        alt_score = self._check_alternating_pattern(recent_trades)
        if alt_score > 0.3:
            scores.append(alt_score * 0.25)
            factors.append(f"alternating_pattern_score={alt_score:.2f}")
            explanations.append("Alternating buy/sell pattern detected")

        # Rule 2: Size symmetry
        size_sym = self._compute_size_symmetry(recent_trades)
        if size_sym > 0.7:
            score = (size_sym - 0.7) / 0.3
            scores.append(score * 0.25)
            factors.append(f"size_symmetry={size_sym:.2f}")
            explanations.append(f"Symmetric trade sizes (symmetry: {size_sym:.2f})")

        # Rule 3: Timing symmetry
        timing_sym = self._compute_timing_symmetry(recent_trades)
        if timing_sym > 0.7:
            score = (timing_sym - 0.7) / 0.3
            scores.append(score * 0.2)
            factors.append(f"timing_symmetry={timing_sym:.2f}")
            explanations.append(f"Regular trade timing (symmetry: {timing_sym:.2f})")

        # Rule 4: Volume recycling
        vol_recycling = self._compute_volume_recycling(recent_trades)
        if vol_recycling > self._volume_recycling_threshold:
            score = (vol_recycling - self._volume_recycling_threshold) / (1.0 - self._volume_recycling_threshold)
            scores.append(score * 0.3)
            factors.append(f"volume_recycling={vol_recycling:.2f}")
            explanations.append(f"High volume recycling ({vol_recycling:.1%})")

        if not scores:
            return None

        total_score = min(1.0, sum(scores))

        if total_score < 0.15:
            return None

        return DetectionResult(
            event_type="wash_trading",
            score=total_score,
            explanation="; ".join(explanations),
            raw_features={
                "alternating_score": alt_score,
                "size_symmetry": size_sym,
                "timing_symmetry": timing_sym,
                "volume_recycling": vol_recycling,
                "trade_count": len(recent_trades),
            },
            detector_name=self.name,
            detector_category=self.category,
            contributing_factors=factors,
            confidence=min(1.0, total_score * 1.1),
        )

    def _check_alternating_pattern(self, trades: List[Dict]) -> float:
        """Check for alternating buy/sell pattern."""
        if len(trades) < 3:
            return 0.0

        alternations = 0
        total_pairs = 0
        for i in range(1, len(trades)):
            side_curr = trades[i].get("side", "")
            side_prev = trades[i - 1].get("side", "")
            if side_curr and side_prev:
                total_pairs += 1
                if side_curr != side_prev:
                    alternations += 1

        return alternations / total_pairs if total_pairs > 0 else 0.0

    def _compute_size_symmetry(self, trades: List[Dict]) -> float:
        """
        Compute size symmetry: 1 - (std/mean) of trade sizes.
        High symmetry (close to 1.0) = similar sizes = suspicious.
        """
        sizes = [float(t.get("quantity", 0)) for t in trades if float(t.get("quantity", 0)) > 0]
        if len(sizes) < 2:
            return 0.0

        mean_size = sum(sizes) / len(sizes)
        if mean_size < 1e-10:
            return 0.0

        variance = sum((s - mean_size) ** 2 for s in sizes) / len(sizes)
        cv = math.sqrt(variance) / mean_size

        return max(0.0, 1.0 - cv)

    def _compute_timing_symmetry(self, trades: List[Dict]) -> float:
        """
        Compute timing symmetry: 1 - (std/mean) of inter-trade intervals.
        High symmetry = regular timing = suspicious.
        """
        from dateutil.parser import parse as parse_date

        timestamps = []
        for t in trades:
            ts = t.get("timestamp", "")
            if isinstance(ts, str) and ts:
                try:
                    timestamps.append(parse_date(ts))
                except (ValueError, TypeError):
                    continue
            elif hasattr(ts, "timestamp"):
                timestamps.append(ts)

        if len(timestamps) < 3:
            return 0.0

        intervals = []
        for i in range(1, len(timestamps)):
            delta = (timestamps[i] - timestamps[i - 1]).total_seconds()
            if delta > 0:
                intervals.append(delta)

        if len(intervals) < 2:
            return 0.0

        mean_interval = sum(intervals) / len(intervals)
        if mean_interval < 1e-10:
            return 0.0

        variance = sum((x - mean_interval) ** 2 for x in intervals) / len(intervals)
        cv = math.sqrt(variance) / mean_interval

        return max(0.0, 1.0 - cv)

    def _compute_volume_recycling(self, trades: List[Dict]) -> float:
        """
        Compute volume recycling ratio: sum(min(buy_vol, sell_vol)) / total_vol.
        High ratio = volume being passed back and forth.
        """
        buy_vol = sum(float(t.get("quantity", 0)) for t in trades
                      if t.get("side") == "buy")
        sell_vol = sum(float(t.get("quantity", 0)) for t in trades
                       if t.get("side") == "sell")
        total = buy_vol + sell_vol

        if total < 1e-10:
            return 0.0

        recycled = min(buy_vol, sell_vol) * 2
        return recycled / total
