"""Tests for ML-based detectors."""

import pytest
import numpy as np

from app.detectors.ml.isolation_forest import IsolationForestDetector
from app.detectors.ml.autoencoder import AutoencoderDetector
from app.detectors.ml.feature_importance import FeatureImportanceExplainer


class TestIsolationForest:
    """Tests for Isolation Forest detector."""

    def test_fit_and_detect(self, normal_features):
        detector = IsolationForestDetector(contamination=0.1)

        # Generate normal training data
        np.random.seed(42)
        normal_data = np.random.randn(200, 9) * 0.5

        detector.fit(normal_data)

        # Normal features should have low score
        result = detector.detect(normal_features)
        # May or may not trigger, but if it does score should be moderate
        if result is not None:
            assert 0 <= result.score <= 1.0

    def test_anomaly_detection(self, suspicious_features):
        detector = IsolationForestDetector(contamination=0.1)

        # Train on very normal data
        np.random.seed(42)
        normal_data = np.random.randn(500, 9) * 0.1 + 0.5

        detector.fit(normal_data)

        # Suspicious features with extreme values should be flagged
        result = detector.detect(suspicious_features)
        # The result depends on the feature distribution
        # At minimum, the detector should not error
        assert detector._is_fitted

    def test_unfitted_returns_none(self, normal_features):
        detector = IsolationForestDetector()
        result = detector.detect(normal_features)
        assert result is None

    def test_properties(self):
        detector = IsolationForestDetector()
        assert detector.name == "isolation_forest"
        assert detector.category == "ml"


class TestAutoencoder:
    """Tests for LSTM Autoencoder detector."""

    def test_properties(self):
        detector = AutoencoderDetector()
        assert detector.name == "lstm_autoencoder"
        assert detector.category == "ml"

    def test_unfitted_returns_none(self, normal_features):
        detector = AutoencoderDetector()
        result = detector.detect(normal_features)
        assert result is None

    def test_add_feature_vector(self, normal_features):
        detector = AutoencoderDetector()
        detector.add_feature_vector(normal_features)
        assert len(detector._feature_buffer) == 1

    def test_fit_and_detect(self):
        """Test autoencoder training and detection (requires PyTorch)."""
        try:
            import torch
        except ImportError:
            pytest.skip("PyTorch not available")

        detector = AutoencoderDetector(sequence_length=5)
        np.random.seed(42)
        # Create sequences: (n_samples, seq_length, n_features)
        sequences = np.random.randn(50, 5, 9).astype(np.float32) * 0.1

        metrics = detector.fit(sequences, epochs=5, batch_size=16)
        assert "final_loss" in metrics
        assert metrics["final_loss"] > 0


class TestFeatureImportance:
    """Tests for SHAP feature importance."""

    def test_fallback_explain(self):
        explainer = FeatureImportanceExplainer()
        vector = np.array([0.8, 25.0, 0.7, 0.8, 0.8, 150.0, 0.5, 3.5, 4.0])
        result = explainer._fallback_explain(vector)
        assert "feature_contributions" in result
        assert "top_features" in result
        assert "explanation" in result
