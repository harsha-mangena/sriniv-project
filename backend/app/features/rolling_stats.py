"""Rolling window statistics for feature computation."""

import math
from collections import deque
from typing import Optional, List
from dataclasses import dataclass


@dataclass
class WindowStats:
    """Statistics computed over a rolling window."""
    mean: float = 0.0
    std: float = 0.0
    min_val: float = 0.0
    max_val: float = 0.0
    count: int = 0
    sum_val: float = 0.0
    zscore_last: float = 0.0


class RollingWindow:
    """
    Efficient rolling window statistics using online algorithms.

    Computes mean, std, min, max, z-score in O(1) amortized time per update.
    Uses Welford's online algorithm for numerically stable variance.
    """

    def __init__(self, window_size: int = 100):
        self._window_size = window_size
        self._values: deque = deque(maxlen=window_size)
        self._sum = 0.0
        self._sum_sq = 0.0
        self._count = 0

    def update(self, value: float) -> WindowStats:
        """Add a new value and return updated statistics."""
        if len(self._values) == self._window_size:
            old_val = self._values[0]
            self._sum -= old_val
            self._sum_sq -= old_val * old_val
        else:
            self._count += 1

        self._values.append(value)
        self._sum += value
        self._sum_sq += value * value

        return self.stats

    @property
    def stats(self) -> WindowStats:
        """Current window statistics."""
        n = len(self._values)
        if n == 0:
            return WindowStats()

        mean = self._sum / n
        variance = max(0.0, (self._sum_sq / n) - (mean * mean))
        std = math.sqrt(variance)

        zscore = 0.0
        if std > 1e-10 and n > 1:
            zscore = (self._values[-1] - mean) / std

        return WindowStats(
            mean=mean,
            std=std,
            min_val=min(self._values),
            max_val=max(self._values),
            count=n,
            sum_val=self._sum,
            zscore_last=zscore,
        )

    @property
    def current_zscore(self) -> float:
        """Z-score of the most recent value."""
        return self.stats.zscore_last

    @property
    def values(self) -> List[float]:
        return list(self._values)

    def reset(self) -> None:
        self._values.clear()
        self._sum = 0.0
        self._sum_sq = 0.0
        self._count = 0


class RollingEntropy:
    """
    Compute Shannon entropy over a rolling window of categorical values.

    Used for volume entropy and order type diversity metrics.
    """

    def __init__(self, window_size: int = 100, num_bins: int = 10):
        self._window_size = window_size
        self._num_bins = num_bins
        self._values: deque = deque(maxlen=window_size)
        self._counts: dict = {}

    def update(self, value: float, bin_edges: Optional[List[float]] = None) -> float:
        """Add a value and return current entropy."""
        # Discretize the value
        bin_idx = self._discretize(value, bin_edges)

        if len(self._values) == self._window_size:
            old_bin = self._values[0]
            self._counts[old_bin] = self._counts.get(old_bin, 1) - 1
            if self._counts[old_bin] <= 0:
                del self._counts[old_bin]

        self._values.append(bin_idx)
        self._counts[bin_idx] = self._counts.get(bin_idx, 0) + 1

        return self.entropy

    def _discretize(self, value: float, bin_edges: Optional[List[float]] = None) -> int:
        """Discretize a continuous value into a bin index."""
        if bin_edges:
            for i, edge in enumerate(bin_edges):
                if value <= edge:
                    return i
            return len(bin_edges)
        # Default: hash-based binning for uniform distribution
        return hash(round(value, 6)) % self._num_bins

    @property
    def entropy(self) -> float:
        """Compute Shannon entropy of the current window."""
        n = len(self._values)
        if n == 0:
            return 0.0

        entropy = 0.0
        for count in self._counts.values():
            if count > 0:
                p = count / n
                entropy -= p * math.log2(p)
        return entropy

    def reset(self) -> None:
        self._values.clear()
        self._counts.clear()


class BurstinessDetector:
    """
    Detect bursty patterns in event arrivals.

    Uses the coefficient of variation of inter-arrival times.
    Burstiness B = (cv - 1) / (cv + 1) where cv = std/mean of inter-arrival times.
    B = 1 for maximally bursty, B = 0 for Poisson, B = -1 for periodic.
    """

    def __init__(self, window_size: int = 100):
        self._window_size = window_size
        self._timestamps: deque = deque(maxlen=window_size + 1)

    def add_event(self, timestamp_ms: float) -> float:
        """Record an event and return current burstiness score."""
        self._timestamps.append(timestamp_ms)
        return self.burstiness

    @property
    def burstiness(self) -> float:
        """Current burstiness score [-1, 1]."""
        if len(self._timestamps) < 3:
            return 0.0

        intervals = []
        ts_list = list(self._timestamps)
        for i in range(1, len(ts_list)):
            intervals.append(ts_list[i] - ts_list[i - 1])

        if not intervals:
            return 0.0

        mean_interval = sum(intervals) / len(intervals)
        if mean_interval < 1e-10:
            return 1.0  # All events at same time = maximally bursty

        variance = sum((x - mean_interval) ** 2 for x in intervals) / len(intervals)
        std_interval = math.sqrt(variance)
        cv = std_interval / mean_interval

        burstiness = (cv - 1) / (cv + 1) if (cv + 1) > 0 else 0.0
        return max(-1.0, min(1.0, burstiness))

    @property
    def event_rate(self) -> float:
        """Events per second."""
        if len(self._timestamps) < 2:
            return 0.0
        duration = (self._timestamps[-1] - self._timestamps[0]) / 1000.0
        if duration < 1e-10:
            return 0.0
        return (len(self._timestamps) - 1) / duration

    def reset(self) -> None:
        self._timestamps.clear()
