"""Abstract base class for all detectors."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field


@dataclass
class DetectionResult:
    """Result from a single detector."""
    event_type: str  # 'spoofing', 'wash_trading', 'layering', 'quote_stuffing', 'anomaly'
    score: float  # 0.0 to 1.0
    explanation: str  # Human-readable explanation
    raw_features: Dict[str, Any] = field(default_factory=dict)
    detector_name: str = ""
    detector_category: str = ""  # 'rule', 'ml', 'custom'
    contributing_factors: List[str] = field(default_factory=list)
    confidence: float = 0.0  # 0.0 to 1.0


class BaseDetector(ABC):
    """Abstract interface for market manipulation detectors."""

    @abstractmethod
    def detect(self, features: Dict[str, Any], **kwargs) -> Optional[DetectionResult]:
        """
        Run detection on computed features.

        Args:
            features: Dict of computed features from FeatureEngine
            **kwargs: Additional context (order_book, recent_trades, etc.)

        Returns:
            DetectionResult if suspicious activity detected, None otherwise.
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Detector name."""
        ...

    @property
    @abstractmethod
    def category(self) -> str:
        """Detector category: 'rule', 'ml', or 'custom'."""
        ...

    @property
    def description(self) -> str:
        """Human-readable description of what this detector looks for."""
        return ""
