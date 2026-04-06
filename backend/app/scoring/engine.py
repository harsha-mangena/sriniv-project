"""Unified scoring engine combining rule, ML, and custom detector outputs."""

from typing import Dict, Any, Optional, List
from datetime import datetime
from collections import defaultdict

from app.detectors.base import BaseDetector, DetectionResult
from app.detectors.rules.spoofing_rules import SpoofingRuleDetector
from app.detectors.rules.wash_rules import WashTradingRuleDetector
from app.detectors.rules.layering_rules import LayeringRuleDetector
from app.detectors.ml.isolation_forest import IsolationForestDetector
from app.detectors.ml.autoencoder import AutoencoderDetector
from app.detectors.custom.liquidity_mirage import LiquidityMirageDetector
from app.detectors.custom.layering_pressure import LayeringPressureDetector
from app.detectors.custom.trade_loop_symmetry import TradeLoopSymmetryDetector
from app.detectors.custom.book_shock import BookShockDivergenceDetector
from app.detectors.custom.intent_outcome import IntentOutcomeMismatchDetector
from app.config import settings
from app.utils.logger import get_logger
from app.utils.time_utils import now_utc

logger = get_logger(__name__)

# Pattern keywords for natural language explanation
PATTERN_DESCRIPTIONS = {
    "spoofing": "Spoofing involves placing large orders to mislead other market participants about supply/demand, then canceling them before execution.",
    "wash_trading": "Wash trading involves simultaneously buying and selling the same asset to create artificial volume and misleading market activity.",
    "layering": "Layering involves placing multiple orders at different price levels to create false depth, then canceling them after trading on the opposite side.",
    "quote_stuffing": "Quote stuffing involves rapidly placing and canceling orders to overwhelm market infrastructure and create latency advantages.",
    "anomaly": "Statistical anomaly detected in market microstructure features that deviates significantly from normal market behavior.",
}


class ScoringEngine:
    """
    Unified scoring engine that orchestrates all detectors and produces
    final scores with natural language explanations.

    Combines:
    - Rule-based detector scores (weight: w_rule)
    - ML anomaly scores (weight: w_ml)
    - Custom microstructure scores (weight: w_custom)

    Produces severity bucketing and explainability output.
    """

    def __init__(self):
        self._w_rule = settings.weight_rule
        self._w_ml = settings.weight_ml
        self._w_custom = settings.weight_custom

        # Initialize all detectors
        self._rule_detectors: List[BaseDetector] = [
            SpoofingRuleDetector(),
            WashTradingRuleDetector(),
            LayeringRuleDetector(),
        ]

        self._ml_detectors: List[BaseDetector] = [
            IsolationForestDetector(),
            AutoencoderDetector(),
        ]

        self._custom_detectors: List[BaseDetector] = [
            LiquidityMirageDetector(),
            LayeringPressureDetector(),
            TradeLoopSymmetryDetector(),
            BookShockDivergenceDetector(),
            IntentOutcomeMismatchDetector(),
        ]

    def evaluate(
        self,
        features: Dict[str, Any],
        **kwargs,
    ) -> Optional[Dict[str, Any]]:
        """
        Run all detectors and produce unified scoring.

        Args:
            features: Computed features from FeatureEngine
            **kwargs: Additional context (order_book, recent_trades)

        Returns:
            Alert dict if score exceeds threshold, None otherwise.
        """
        rule_results = self._run_detectors(self._rule_detectors, features, **kwargs)
        ml_results = self._run_detectors(self._ml_detectors, features, **kwargs)
        custom_results = self._run_detectors(self._custom_detectors, features, **kwargs)

        all_results = rule_results + ml_results + custom_results

        if not all_results:
            return None

        # Compute weighted final score
        rule_max = max((r.score for r in rule_results), default=0.0)
        ml_max = max((r.score for r in ml_results), default=0.0)
        custom_scores = [r.score for r in custom_results]
        custom_avg = sum(custom_scores) / len(custom_scores) if custom_scores else 0.0

        final_score = (
            self._w_rule * rule_max +
            self._w_ml * ml_max +
            self._w_custom * custom_avg
        ) * 100

        final_score = min(100.0, max(0.0, final_score))

        # Severity bucketing
        severity = self._compute_severity(final_score)

        # Skip low-confidence alerts
        if severity == "low" and final_score < 15:
            return None

        # Determine primary alert type
        alert_type = self._determine_alert_type(all_results)

        # Build explanation
        explanation = self._build_explanation(all_results, alert_type, final_score, severity)

        # Build scores breakdown
        rule_scores = {r.detector_name: r.score for r in rule_results}
        ml_scores_dict = {r.detector_name: r.score for r in ml_results}
        custom_scores_dict = {r.detector_name: r.score for r in custom_results}

        # Contributing features
        contributing_features = {}
        for result in all_results:
            contributing_features.update(result.raw_features)

        return {
            "symbol": features.get("symbol", "unknown"),
            "alert_type": alert_type,
            "severity": severity,
            "confidence_score": round(final_score, 2),
            "rule_scores": rule_scores,
            "ml_scores": ml_scores_dict,
            "custom_scores": custom_scores_dict,
            "explanation": explanation,
            "contributing_features": contributing_features,
            "raw_evidence": {
                "features": features,
                "fired_detectors": [r.detector_name for r in all_results],
            },
            "timestamp": now_utc().isoformat(),
        }

    def _run_detectors(
        self,
        detectors: List[BaseDetector],
        features: Dict[str, Any],
        **kwargs,
    ) -> List[DetectionResult]:
        """Run a list of detectors and collect results."""
        results = []
        for detector in detectors:
            try:
                result = detector.detect(features, **kwargs)
                if result is not None:
                    results.append(result)
            except Exception as e:
                logger.error(
                    "detector_error",
                    detector=detector.name,
                    error=str(e),
                )
        return results

    @staticmethod
    def _compute_severity(score: float) -> str:
        """Bucket score into severity level."""
        if score > 85:
            return "critical"
        elif score > 65:
            return "high"
        elif score > 40:
            return "medium"
        else:
            return "low"

    @staticmethod
    def _determine_alert_type(results: List[DetectionResult]) -> str:
        """Determine the primary alert type from detector results."""
        type_scores = defaultdict(float)
        for result in results:
            type_scores[result.event_type] += result.score

        if not type_scores:
            return "anomaly"

        return max(type_scores, key=type_scores.get)

    def _build_explanation(
        self,
        results: List[DetectionResult],
        alert_type: str,
        score: float,
        severity: str,
    ) -> str:
        """Generate natural language explanation of the alert."""
        parts = []

        # Header
        parts.append(
            f"[{severity.upper()}] {alert_type.replace('_', ' ').title()} Alert "
            f"(confidence: {score:.1f}/100)"
        )

        # Pattern description
        desc = PATTERN_DESCRIPTIONS.get(alert_type, "Unusual market activity detected.")
        parts.append(f"\nPattern: {desc}")

        # Detector findings
        parts.append("\nDetector findings:")
        for result in sorted(results, key=lambda r: r.score, reverse=True):
            category_label = {
                "rule": "Rule-Based",
                "ml": "ML",
                "custom": "Microstructure",
            }.get(result.detector_category, result.detector_category)
            parts.append(
                f"  - [{category_label}] {result.detector_name}: "
                f"score={result.score:.2f} — {result.explanation}"
            )

        # Key contributing factors
        all_factors = []
        for result in results:
            all_factors.extend(result.contributing_factors)
        if all_factors:
            parts.append(f"\nKey factors: {'; '.join(all_factors[:5])}")

        return "\n".join(parts)

    @property
    def rule_detectors(self) -> List[BaseDetector]:
        return self._rule_detectors

    @property
    def ml_detectors(self) -> List[BaseDetector]:
        return self._ml_detectors

    @property
    def custom_detectors(self) -> List[BaseDetector]:
        return self._custom_detectors

    def get_ml_detector(self, name: str) -> Optional[BaseDetector]:
        """Get an ML detector by name for training/loading."""
        for d in self._ml_detectors:
            if d.name == name:
                return d
        return None
