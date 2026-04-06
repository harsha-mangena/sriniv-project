"""Unit tests for rule-based detectors."""

import pytest
from datetime import datetime, timezone, timedelta

from app.detectors.rules.spoofing_rules import SpoofingRuleDetector
from app.detectors.rules.wash_rules import WashTradingRuleDetector
from app.detectors.rules.layering_rules import LayeringRuleDetector


class TestSpoofingRules:
    """Tests for spoofing rule detector."""

    def test_high_cancel_rate_detected(self, suspicious_features):
        detector = SpoofingRuleDetector(cancel_rate_threshold=0.7)
        result = detector.detect(suspicious_features)
        assert result is not None
        assert result.event_type == "spoofing"
        assert result.score > 0

    def test_normal_not_flagged(self, normal_features):
        detector = SpoofingRuleDetector()
        result = detector.detect(normal_features)
        # Normal features should not trigger or have very low score
        if result is not None:
            assert result.score < 0.3

    def test_short_lifetime_flagged(self, suspicious_features):
        detector = SpoofingRuleDetector(lifetime_threshold_ms=500)
        result = detector.detect(suspicious_features)
        assert result is not None
        assert any("lifetime" in f for f in result.contributing_factors)

    def test_detector_properties(self):
        detector = SpoofingRuleDetector()
        assert detector.name == "spoofing_rules"
        assert detector.category == "rule"


class TestWashTradingRules:
    """Tests for wash trading rule detector."""

    def test_symmetric_trades_detected(self, normal_features, wash_trading_trades):
        detector = WashTradingRuleDetector()
        result = detector.detect(normal_features, recent_trades=wash_trading_trades)
        assert result is not None
        assert result.event_type == "wash_trading"
        assert result.score > 0

    def test_insufficient_trades(self, normal_features):
        detector = WashTradingRuleDetector(min_trades=4)
        result = detector.detect(normal_features, recent_trades=[
            {"side": "buy", "quantity": 1.0, "timestamp": "2024-01-01T00:00:00Z"},
        ])
        assert result is None

    def test_random_trades_low_score(self, normal_features):
        import random
        random.seed(42)
        trades = [
            {
                "side": random.choice(["buy", "sell"]),
                "quantity": random.uniform(0.01, 10.0),
                "price": 50000 + random.gauss(0, 100),
                "timestamp": f"2024-01-15T12:00:{i:02d}Z",
                "trade_id": f"R{i}",
            }
            for i in range(30)
        ]
        detector = WashTradingRuleDetector()
        result = detector.detect(normal_features, recent_trades=trades)
        # Random trades should have lower score than symmetric ones
        if result is not None:
            assert result.score < 0.5

    def test_detector_properties(self):
        detector = WashTradingRuleDetector()
        assert detector.name == "wash_trading_rules"
        assert detector.category == "rule"


class TestLayeringRules:
    """Tests for layering rule detector."""

    def test_high_concentration_detected(self, suspicious_features):
        detector = LayeringRuleDetector(depth_concentration_threshold=0.6)
        result = detector.detect(suspicious_features)
        assert result is not None
        assert result.event_type == "layering"
        assert result.score > 0

    def test_normal_not_flagged(self, normal_features):
        detector = LayeringRuleDetector()
        result = detector.detect(normal_features)
        if result is not None:
            assert result.score < 0.3

    def test_detector_properties(self):
        detector = LayeringRuleDetector()
        assert detector.name == "layering_rules"
        assert detector.category == "rule"
