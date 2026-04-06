"""Tests for the unified scoring engine."""

import pytest

from app.scoring.engine import ScoringEngine
from app.detectors.base import DetectionResult


class TestScoringEngine:
    """Tests for ScoringEngine."""

    def test_initialization(self, scoring_engine):
        assert len(scoring_engine.rule_detectors) == 3
        assert len(scoring_engine.ml_detectors) == 2
        assert len(scoring_engine.custom_detectors) == 5

    def test_normal_features_no_alert(self, scoring_engine, normal_features):
        alert = scoring_engine.evaluate(normal_features)
        # Normal features might produce a low-severity alert or None
        if alert is not None:
            assert alert["severity"] in ("low", "medium")

    def test_suspicious_features_alert(self, scoring_engine, suspicious_features):
        alert = scoring_engine.evaluate(suspicious_features)
        # Suspicious features should produce an alert
        assert alert is not None
        assert alert["confidence_score"] > 0
        assert alert["severity"] in ("low", "medium", "high", "critical")
        assert alert["explanation"]

    def test_alert_structure(self, scoring_engine, suspicious_features):
        alert = scoring_engine.evaluate(suspicious_features)
        assert alert is not None
        assert "symbol" in alert
        assert "alert_type" in alert
        assert "severity" in alert
        assert "confidence_score" in alert
        assert "rule_scores" in alert
        assert "ml_scores" in alert
        assert "custom_scores" in alert
        assert "explanation" in alert
        assert "timestamp" in alert

    def test_severity_bucketing(self):
        assert ScoringEngine._compute_severity(90.0) == "critical"
        assert ScoringEngine._compute_severity(70.0) == "high"
        assert ScoringEngine._compute_severity(50.0) == "medium"
        assert ScoringEngine._compute_severity(20.0) == "low"

    def test_alert_type_determination(self):
        results = [
            DetectionResult(event_type="spoofing", score=0.8, explanation="test", detector_name="r1", detector_category="rule"),
            DetectionResult(event_type="spoofing", score=0.5, explanation="test", detector_name="r2", detector_category="custom"),
            DetectionResult(event_type="wash_trading", score=0.3, explanation="test", detector_name="r3", detector_category="rule"),
        ]
        alert_type = ScoringEngine._determine_alert_type(results)
        assert alert_type == "spoofing"  # Highest aggregate score

    def test_explanation_generated(self, scoring_engine, suspicious_features):
        alert = scoring_engine.evaluate(suspicious_features)
        assert alert is not None
        assert len(alert["explanation"]) > 50
        assert "Alert" in alert["explanation"] or "Detector" in alert["explanation"].lower() or "findings" in alert["explanation"].lower()

    def test_get_ml_detector(self, scoring_engine):
        ifo = scoring_engine.get_ml_detector("isolation_forest")
        assert ifo is not None
        assert ifo.name == "isolation_forest"

        ae = scoring_engine.get_ml_detector("lstm_autoencoder")
        assert ae is not None

        missing = scoring_engine.get_ml_detector("nonexistent")
        assert missing is None
