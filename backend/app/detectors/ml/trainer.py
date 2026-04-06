"""ML model training pipeline."""

from typing import Dict, Any, Optional, List
import numpy as np

from app.detectors.ml.isolation_forest import IsolationForestDetector
from app.detectors.ml.autoencoder import AutoencoderDetector
from app.features.feature_engine import FeatureEngine
from app.ingestion.synthetic import SyntheticDataGenerator
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class MLTrainer:
    """
    Training pipeline for ML-based detectors.

    Generates synthetic normal market data, extracts features, and trains
    both the Isolation Forest and LSTM Autoencoder models.
    """

    def __init__(self):
        self._feature_engine = FeatureEngine()
        self._isolation_forest = IsolationForestDetector()
        self._autoencoder = AutoencoderDetector()

    async def generate_training_data(
        self,
        n_samples: int = 5000,
        symbol: str = "btcusdt",
    ) -> np.ndarray:
        """
        Generate synthetic normal trading data for training.

        Returns:
            Feature matrix of shape (n_samples, n_features)
        """
        logger.info("generating_training_data", n_samples=n_samples)

        generator = SyntheticDataGenerator(
            symbol=symbol,
            base_price=50000.0,
            events_per_second=50.0,
            manipulation_probability=0.0,  # Normal data only
        )
        await generator.connect()

        feature_vectors = []
        event_count = 0

        async for event in generator.stream():
            self._feature_engine.process_event(event)
            event_count += 1

            # Compute features every 10 events
            if event_count % 10 == 0:
                features = self._feature_engine.compute_features(symbol)
                vector = self._feature_engine.get_feature_vector(symbol)
                feature_vectors.append(vector)

            if len(feature_vectors) >= n_samples:
                break

        await generator.disconnect()

        matrix = np.array(feature_vectors, dtype=np.float32)
        logger.info("training_data_generated", shape=matrix.shape)
        return matrix

    def train_isolation_forest(self, feature_matrix: np.ndarray) -> Dict[str, Any]:
        """Train the Isolation Forest model."""
        logger.info("training_isolation_forest", n_samples=feature_matrix.shape[0])
        self._isolation_forest.fit(feature_matrix)
        model_path = self._isolation_forest.save()
        return {
            "model": "isolation_forest",
            "n_samples": feature_matrix.shape[0],
            "n_features": feature_matrix.shape[1],
            "model_path": model_path,
        }

    def train_autoencoder(
        self,
        feature_matrix: np.ndarray,
        sequence_length: int = 20,
        epochs: int = None,
    ) -> Dict[str, Any]:
        """Train the LSTM Autoencoder model."""
        epochs = epochs or settings.autoencoder_epochs

        # Create sequences from feature matrix
        sequences = self._create_sequences(feature_matrix, sequence_length)
        if sequences is None or len(sequences) < 10:
            return {"error": "Not enough data for sequence training"}

        logger.info("training_autoencoder", n_sequences=sequences.shape[0], epochs=epochs)
        metrics = self._autoencoder.fit(sequences, epochs=epochs)
        model_path = self._autoencoder.save()

        return {
            "model": "autoencoder",
            "n_sequences": sequences.shape[0],
            "sequence_length": sequence_length,
            "model_path": model_path,
            **metrics,
        }

    async def train_all(
        self,
        n_samples: int = 5000,
        autoencoder_epochs: int = None,
    ) -> Dict[str, Any]:
        """Train all ML models."""
        # Generate training data
        feature_matrix = await self.generate_training_data(n_samples)

        # Train models
        if_results = self.train_isolation_forest(feature_matrix)
        ae_results = self.train_autoencoder(feature_matrix, epochs=autoencoder_epochs)

        return {
            "isolation_forest": if_results,
            "autoencoder": ae_results,
            "total_samples": feature_matrix.shape[0],
        }

    @staticmethod
    def _create_sequences(matrix: np.ndarray, seq_length: int) -> Optional[np.ndarray]:
        """Create overlapping sequences from a feature matrix."""
        if matrix.shape[0] < seq_length:
            return None

        sequences = []
        for i in range(matrix.shape[0] - seq_length + 1):
            sequences.append(matrix[i:i + seq_length])

        return np.array(sequences, dtype=np.float32)

    @property
    def isolation_forest(self) -> IsolationForestDetector:
        return self._isolation_forest

    @property
    def autoencoder(self) -> AutoencoderDetector:
        return self._autoencoder
