"""Isolation Forest anomaly detection for market manipulation."""

import os
import pickle
from typing import Dict, Any, Optional, List

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from app.detectors.base import BaseDetector, DetectionResult
from app.features.feature_engine import FeatureEngine
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class IsolationForestDetector(BaseDetector):
    """
    Isolation Forest-based anomaly detection.

    Trained on "normal" market periods to identify anomalous feature vectors.
    Features: cancel_rate, order_to_trade_ratio, bid_ask_imbalance,
    depth_concentration, burstiness, avg_order_lifetime, volume_entropy,
    rolling z-scores.
    """

    def __init__(
        self,
        contamination: float = None,
        n_estimators: int = 200,
        max_samples: int = 256,
        random_state: int = 42,
    ):
        self._contamination = contamination or settings.isolation_forest_contamination
        self._n_estimators = n_estimators
        self._max_samples = max_samples
        self._random_state = random_state
        self._model: Optional[IsolationForest] = None
        self._scaler: Optional[StandardScaler] = None
        self._is_fitted = False
        self._feature_names = FeatureEngine.feature_names()

    @property
    def name(self) -> str:
        return "isolation_forest"

    @property
    def category(self) -> str:
        return "ml"

    @property
    def description(self) -> str:
        return "Isolation Forest anomaly detection trained on normal market behavior"

    def fit(self, feature_matrix: np.ndarray) -> None:
        """
        Train the Isolation Forest on normal market data.

        Args:
            feature_matrix: (n_samples, n_features) array of normal market features
        """
        logger.info("isolation_forest_training", n_samples=feature_matrix.shape[0])

        self._scaler = StandardScaler()
        X_scaled = self._scaler.fit_transform(feature_matrix)

        self._model = IsolationForest(
            contamination=self._contamination,
            n_estimators=self._n_estimators,
            max_samples=min(self._max_samples, X_scaled.shape[0]),
            random_state=self._random_state,
            n_jobs=-1,
        )
        self._model.fit(X_scaled)
        self._is_fitted = True

        logger.info("isolation_forest_trained", n_features=feature_matrix.shape[1])

    def detect(self, features: Dict[str, Any], **kwargs) -> Optional[DetectionResult]:
        """Run anomaly detection on feature vector."""
        if not self._is_fitted:
            return None

        # Extract feature vector
        feature_vector = self._extract_features(features)
        if feature_vector is None:
            return None

        X = np.array([feature_vector])
        X_scaled = self._scaler.transform(X)

        # Get anomaly score (-1 for anomaly, 1 for normal)
        prediction = self._model.predict(X_scaled)[0]
        # Score function: lower = more anomalous
        raw_score = self._model.score_samples(X_scaled)[0]

        # Convert to 0-1 anomaly score (higher = more anomalous)
        # score_samples returns negative values, more negative = more anomalous
        # Typical range is roughly [-0.7, 0.0] for normal, < -0.7 for anomalies
        anomaly_score = max(0.0, min(1.0, -raw_score - 0.3))

        if prediction == 1 and anomaly_score < 0.3:
            return None

        # Identify which features contributed most
        contributing = self._identify_contributing_features(feature_vector)

        return DetectionResult(
            event_type="anomaly",
            score=anomaly_score,
            explanation=f"Isolation Forest anomaly score: {anomaly_score:.2f}. "
                        f"Contributing features: {', '.join(contributing[:3])}",
            raw_features={
                "raw_score": float(raw_score),
                "anomaly_score": float(anomaly_score),
                "prediction": int(prediction),
                "feature_vector": feature_vector,
            },
            detector_name=self.name,
            detector_category=self.category,
            contributing_factors=contributing,
            confidence=anomaly_score,
        )

    def _extract_features(self, features: Dict[str, Any]) -> Optional[List[float]]:
        """Extract ordered feature vector from features dict."""
        try:
            return [
                float(features.get("cancel_rate", 0)),
                float(features.get("order_to_trade_ratio", 0)),
                float(features.get("bid_ask_imbalance", 0)),
                float(features.get("depth_concentration", 0)),
                float(features.get("order_arrival_burstiness", 0)),
                float(features.get("avg_order_lifetime_ms", 0)),
                float(features.get("volume_entropy", 0)),
                float(features.get("rolling_zscore_volume", 0)),
                float(features.get("rolling_zscore_cancel", 0)),
            ]
        except (TypeError, ValueError):
            return None

    def _identify_contributing_features(self, feature_vector: List[float]) -> List[str]:
        """Identify features most contributing to anomaly (by z-score from training mean)."""
        if self._scaler is None:
            return []

        X = np.array([feature_vector])
        X_scaled = self._scaler.transform(X)[0]

        # Features with highest absolute scaled values contribute most
        feature_importance = list(zip(self._feature_names, np.abs(X_scaled)))
        feature_importance.sort(key=lambda x: x[1], reverse=True)

        return [
            f"{name} (z={abs_z:.2f})"
            for name, abs_z in feature_importance
            if abs_z > 1.0
        ]

    def save(self, path: Optional[str] = None) -> str:
        """Save model and scaler to disk."""
        model_dir = path or settings.ml_model_dir
        os.makedirs(model_dir, exist_ok=True)

        model_path = os.path.join(model_dir, "isolation_forest.pkl")
        with open(model_path, "wb") as f:
            pickle.dump({"model": self._model, "scaler": self._scaler}, f)

        logger.info("isolation_forest_saved", path=model_path)
        return model_path

    def load(self, path: Optional[str] = None) -> bool:
        """Load model and scaler from disk."""
        model_dir = path or settings.ml_model_dir
        model_path = os.path.join(model_dir, "isolation_forest.pkl")

        if not os.path.exists(model_path):
            logger.warning("isolation_forest_not_found", path=model_path)
            return False

        with open(model_path, "rb") as f:
            data = pickle.load(f)
            self._model = data["model"]
            self._scaler = data["scaler"]
            self._is_fitted = True

        logger.info("isolation_forest_loaded", path=model_path)
        return True
