"""SHAP-based feature importance for explainability."""

from typing import Dict, Any, Optional, List
import numpy as np

from app.features.feature_engine import FeatureEngine
from app.utils.logger import get_logger

logger = get_logger(__name__)

try:
    import shap
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False


class FeatureImportanceExplainer:
    """
    SHAP-based feature importance for explaining anomaly detections.

    Uses SHAP (SHapley Additive exPlanations) to explain which features
    drove the anomaly score for a specific detection.
    """

    def __init__(self):
        self._feature_names = FeatureEngine.feature_names()
        self._explainer = None
        self._background_data = None

    def fit(self, model, background_data: np.ndarray) -> None:
        """
        Initialize SHAP explainer with a trained model.

        Args:
            model: sklearn model (e.g., IsolationForest) with predict method
            background_data: Representative sample of normal data for SHAP
        """
        if not SHAP_AVAILABLE:
            logger.warning("shap_unavailable", msg="SHAP package not installed")
            return

        self._background_data = background_data
        # Use a subsample for efficiency
        n_background = min(100, background_data.shape[0])
        bg_sample = background_data[:n_background]

        try:
            # Use KernelExplainer for model-agnostic explanations
            self._explainer = shap.KernelExplainer(
                model.score_samples,
                bg_sample,
            )
            logger.info("shap_explainer_initialized", n_background=n_background)
        except Exception as e:
            logger.error("shap_init_failed", error=str(e))
            self._explainer = None

    def explain(self, feature_vector: np.ndarray) -> Dict[str, Any]:
        """
        Explain a detection by computing SHAP values.

        Args:
            feature_vector: (n_features,) or (1, n_features) array

        Returns:
            Dict with SHAP values, feature importances, and explanation text
        """
        if not SHAP_AVAILABLE or self._explainer is None:
            return self._fallback_explain(feature_vector)

        if feature_vector.ndim == 1:
            feature_vector = feature_vector.reshape(1, -1)

        try:
            shap_values = self._explainer.shap_values(feature_vector, nsamples=50)
            if isinstance(shap_values, list):
                shap_values = shap_values[0]

            shap_vals = shap_values[0] if shap_values.ndim > 1 else shap_values

            # Build explanation
            feature_contributions = []
            for i, (name, val) in enumerate(zip(self._feature_names, shap_vals)):
                feature_contributions.append({
                    "feature": name,
                    "shap_value": float(val),
                    "feature_value": float(feature_vector[0][i]),
                    "impact": "increases" if val > 0 else "decreases",
                })

            # Sort by absolute SHAP value
            feature_contributions.sort(key=lambda x: abs(x["shap_value"]), reverse=True)

            # Generate text explanation
            top_features = feature_contributions[:3]
            explanation_parts = []
            for fc in top_features:
                direction = "increasing" if fc["shap_value"] > 0 else "decreasing"
                explanation_parts.append(
                    f"{fc['feature']}={fc['feature_value']:.4f} ({direction} anomaly score by {abs(fc['shap_value']):.4f})"
                )

            return {
                "shap_values": {name: float(val) for name, val in zip(self._feature_names, shap_vals)},
                "feature_contributions": feature_contributions,
                "top_features": [f["feature"] for f in top_features],
                "explanation": "Key drivers: " + "; ".join(explanation_parts),
            }

        except Exception as e:
            logger.error("shap_explain_failed", error=str(e))
            return self._fallback_explain(feature_vector)

    def _fallback_explain(self, feature_vector: np.ndarray) -> Dict[str, Any]:
        """Fallback explanation when SHAP is unavailable."""
        if feature_vector.ndim > 1:
            feature_vector = feature_vector[0]

        # Simple z-score based explanation
        feature_contributions = []
        for i, (name, val) in enumerate(zip(self._feature_names, feature_vector)):
            feature_contributions.append({
                "feature": name,
                "feature_value": float(val),
                "abs_value": abs(float(val)),
            })

        feature_contributions.sort(key=lambda x: x["abs_value"], reverse=True)
        top_features = feature_contributions[:3]

        explanation_parts = [
            f"{f['feature']}={f['feature_value']:.4f}" for f in top_features
        ]

        return {
            "feature_contributions": feature_contributions,
            "top_features": [f["feature"] for f in top_features],
            "explanation": "Most extreme features: " + "; ".join(explanation_parts),
            "method": "fallback_zscore",
        }
