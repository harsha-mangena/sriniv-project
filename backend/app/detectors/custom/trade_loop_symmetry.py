"""Trade Loop Symmetry Score (TLSS) - detects wash trading patterns.

For sliding windows of trades:
  1. Group trades by approximate size (within tolerance %)
  2. Check alternating buy/sell pattern
  3. timing_symmetry = std_dev(intervals) / mean(intervals)
  4. size_symmetry = std_dev(sizes) / mean(sizes)
  5. volume_recycling = sum(min(buy_vol, sell_vol)) / total_volume

TLSS = (1 - timing_symmetry) * (1 - size_symmetry) * volume_recycling * loop_frequency
"""

import math
from typing import Dict, Any, Optional, List
from collections import defaultdict

from app.detectors.base import BaseDetector, DetectionResult


class TradeLoopSymmetryDetector(BaseDetector):
    """
    Trade Loop Symmetry Score detector for wash trading.

    Identifies wash trading patterns by detecting symmetric trade loops:
    - Similar-sized trades alternating between buy and sell
    - Regular timing between trades
    - High volume recycling ratio
    """

    def __init__(
        self,
        size_tolerance: float = 0.05,
        min_loop_trades: int = 4,
        window_size: int = 50,
        threshold: float = 0.4,
    ):
        self._size_tolerance = size_tolerance
        self._min_loop_trades = min_loop_trades
        self._window_size = window_size
        self._threshold = threshold

    @property
    def name(self) -> str:
        return "trade_loop_symmetry"

    @property
    def category(self) -> str:
        return "custom"

    @property
    def description(self) -> str:
        return "Trade Loop Symmetry Score detecting wash trading via symmetric trade patterns"

    def detect(self, features: Dict[str, Any], **kwargs) -> Optional[DetectionResult]:
        """Compute TLSS and flag if above threshold."""
        recent_trades: List[Dict] = kwargs.get("recent_trades", [])

        if len(recent_trades) < self._min_loop_trades:
            return None

        # Analyze sliding windows
        trades = recent_trades[-self._window_size:]
        tlss, components = self._compute_tlss(trades)

        if tlss < self._threshold:
            return None

        score = min(1.0, tlss)

        contributing = []
        if components.get("timing_symmetry", 0) > 0.5:
            contributing.append(f"timing_symmetry={components['timing_symmetry']:.2f}")
        if components.get("size_symmetry", 0) > 0.5:
            contributing.append(f"size_symmetry={components['size_symmetry']:.2f}")
        if components.get("volume_recycling", 0) > 0.5:
            contributing.append(f"volume_recycling={components['volume_recycling']:.2f}")
        if components.get("loop_frequency", 0) > 0.3:
            contributing.append(f"loop_frequency={components['loop_frequency']:.2f}")

        return DetectionResult(
            event_type="wash_trading",
            score=score,
            explanation=f"Trade Loop Symmetry Score: {tlss:.3f}. "
                        f"Detected symmetric buy-sell loops with "
                        f"volume recycling of {components.get('volume_recycling', 0):.1%}.",
            raw_features={
                "tlss": tlss,
                **components,
                "trade_count": len(trades),
            },
            detector_name=self.name,
            detector_category=self.category,
            contributing_factors=contributing,
            confidence=min(1.0, score * 1.1),
        )

    def _compute_tlss(self, trades: List[Dict]) -> tuple:
        """Compute the Trade Loop Symmetry Score."""
        if len(trades) < self._min_loop_trades:
            return 0.0, {}

        # Step 1 & 2: Group by size and check alternating pattern
        size_groups = self._group_by_size(trades)
        best_loop_score = 0.0
        best_components = {}

        for group_key, group_trades in size_groups.items():
            if len(group_trades) < self._min_loop_trades:
                continue

            # Step 3: Timing symmetry
            timing_cv = self._compute_timing_cv(group_trades)
            timing_sym = max(0.0, 1.0 - timing_cv)

            # Step 4: Size symmetry
            size_cv = self._compute_size_cv(group_trades)
            size_sym = max(0.0, 1.0 - size_cv)

            # Step 5: Volume recycling
            vol_recycling = self._compute_volume_recycling(group_trades)

            # Loop frequency: how many complete buy-sell loops
            loop_freq = self._compute_loop_frequency(group_trades)

            # TLSS formula
            tlss = timing_sym * size_sym * vol_recycling * loop_freq

            if tlss > best_loop_score:
                best_loop_score = tlss
                best_components = {
                    "timing_symmetry": timing_sym,
                    "size_symmetry": size_sym,
                    "volume_recycling": vol_recycling,
                    "loop_frequency": loop_freq,
                    "timing_cv": timing_cv,
                    "size_cv": size_cv,
                    "group_size": len(group_trades),
                }

        # Also compute on all trades (without size grouping)
        all_timing_cv = self._compute_timing_cv(trades)
        all_size_cv = self._compute_size_cv(trades)
        all_vol_recycling = self._compute_volume_recycling(trades)
        all_loop_freq = self._compute_loop_frequency(trades)

        all_tlss = max(0.0, 1.0 - all_timing_cv) * max(0.0, 1.0 - all_size_cv) * all_vol_recycling * all_loop_freq

        if all_tlss > best_loop_score:
            best_loop_score = all_tlss
            best_components = {
                "timing_symmetry": max(0.0, 1.0 - all_timing_cv),
                "size_symmetry": max(0.0, 1.0 - all_size_cv),
                "volume_recycling": all_vol_recycling,
                "loop_frequency": all_loop_freq,
                "timing_cv": all_timing_cv,
                "size_cv": all_size_cv,
                "group_size": len(trades),
            }

        return best_loop_score, best_components

    def _group_by_size(self, trades: List[Dict]) -> Dict[str, List[Dict]]:
        """Group trades by approximate size within tolerance."""
        groups: Dict[str, List[Dict]] = defaultdict(list)

        for trade in trades:
            qty = float(trade.get("quantity", 0))
            if qty <= 0:
                continue
            # Create size bucket
            bucket = round(qty / (qty * self._size_tolerance + 0.001)) if qty > 0 else 0
            groups[str(bucket)].append(trade)

        return groups

    def _compute_timing_cv(self, trades: List[Dict]) -> float:
        """Coefficient of variation of inter-trade intervals."""
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
            return 1.0  # High CV = not symmetric

        intervals = []
        for i in range(1, len(timestamps)):
            delta = abs((timestamps[i] - timestamps[i - 1]).total_seconds())
            if delta > 0:
                intervals.append(delta)

        if len(intervals) < 2:
            return 1.0

        mean_interval = sum(intervals) / len(intervals)
        if mean_interval < 1e-10:
            return 1.0

        variance = sum((x - mean_interval) ** 2 for x in intervals) / len(intervals)
        cv = math.sqrt(variance) / mean_interval
        return min(2.0, cv)

    def _compute_size_cv(self, trades: List[Dict]) -> float:
        """Coefficient of variation of trade sizes."""
        sizes = [float(t.get("quantity", 0)) for t in trades if float(t.get("quantity", 0)) > 0]
        if len(sizes) < 2:
            return 1.0

        mean_size = sum(sizes) / len(sizes)
        if mean_size < 1e-10:
            return 1.0

        variance = sum((s - mean_size) ** 2 for s in sizes) / len(sizes)
        cv = math.sqrt(variance) / mean_size
        return min(2.0, cv)

    def _compute_volume_recycling(self, trades: List[Dict]) -> float:
        """Volume recycling ratio: 2*min(buy_vol, sell_vol) / total_vol."""
        buy_vol = sum(float(t.get("quantity", 0)) for t in trades if t.get("side") == "buy")
        sell_vol = sum(float(t.get("quantity", 0)) for t in trades if t.get("side") == "sell")
        total = buy_vol + sell_vol

        if total < 1e-10:
            return 0.0

        return (2 * min(buy_vol, sell_vol)) / total

    def _compute_loop_frequency(self, trades: List[Dict]) -> float:
        """Count complete buy-sell loops normalized by trade count."""
        if len(trades) < 2:
            return 0.0

        loops = 0
        for i in range(1, len(trades)):
            curr_side = trades[i].get("side", "")
            prev_side = trades[i - 1].get("side", "")
            if curr_side and prev_side and curr_side != prev_side:
                loops += 0.5  # Each alternation is half a loop

        max_possible = len(trades) / 2
        return min(1.0, loops / max_possible) if max_possible > 0 else 0.0
