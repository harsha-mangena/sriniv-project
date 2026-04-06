"""LSTM Autoencoder for sequence anomaly detection using PyTorch."""

import os
from typing import Dict, Any, Optional, List, Tuple

import numpy as np

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

from app.detectors.base import BaseDetector, DetectionResult
from app.features.feature_engine import FeatureEngine
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


if TORCH_AVAILABLE:
    class LSTMAutoencoder(nn.Module):
        """LSTM-based autoencoder for sequence anomaly detection."""

        def __init__(self, input_dim: int, hidden_dim: int, latent_dim: int, num_layers: int = 2):
            super().__init__()
            self.input_dim = input_dim
            self.hidden_dim = hidden_dim
            self.latent_dim = latent_dim
            self.num_layers = num_layers

            # Encoder
            self.encoder_lstm = nn.LSTM(
                input_size=input_dim,
                hidden_size=hidden_dim,
                num_layers=num_layers,
                batch_first=True,
                dropout=0.1 if num_layers > 1 else 0,
            )
            self.encoder_fc = nn.Linear(hidden_dim, latent_dim)

            # Decoder
            self.decoder_fc = nn.Linear(latent_dim, hidden_dim)
            self.decoder_lstm = nn.LSTM(
                input_size=hidden_dim,
                hidden_size=hidden_dim,
                num_layers=num_layers,
                batch_first=True,
                dropout=0.1 if num_layers > 1 else 0,
            )
            self.output_fc = nn.Linear(hidden_dim, input_dim)

        def encode(self, x: torch.Tensor) -> torch.Tensor:
            """Encode sequence to latent representation."""
            _, (hidden, _) = self.encoder_lstm(x)
            # Use last layer's hidden state
            latent = self.encoder_fc(hidden[-1])
            return latent

        def decode(self, latent: torch.Tensor, seq_len: int) -> torch.Tensor:
            """Decode latent representation back to sequence."""
            hidden = self.decoder_fc(latent)
            # Repeat latent vector for each timestep
            decoder_input = hidden.unsqueeze(1).repeat(1, seq_len, 1)
            decoder_output, _ = self.decoder_lstm(decoder_input)
            reconstruction = self.output_fc(decoder_output)
            return reconstruction

        def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
            """Forward pass: encode then decode."""
            seq_len = x.size(1)
            latent = self.encode(x)
            reconstruction = self.decode(latent, seq_len)
            return reconstruction, latent


class AutoencoderDetector(BaseDetector):
    """
    LSTM Autoencoder anomaly detector.

    Trains on sequences of normal feature vectors. Anomalies are detected
    by high reconstruction error - the model cannot reconstruct unusual patterns.
    """

    def __init__(
        self,
        sequence_length: int = 20,
        hidden_dim: int = None,
        latent_dim: int = None,
        threshold_percentile: float = 95.0,
    ):
        self._seq_length = sequence_length
        self._hidden_dim = hidden_dim or settings.autoencoder_hidden_dim
        self._latent_dim = latent_dim or settings.autoencoder_latent_dim
        self._threshold_percentile = threshold_percentile
        self._model = None
        self._threshold = None
        self._is_fitted = False
        self._feature_names = FeatureEngine.feature_names()
        self._input_dim = len(self._feature_names)
        self._feature_buffer: List[List[float]] = []
        self._mean: Optional[np.ndarray] = None
        self._std: Optional[np.ndarray] = None
        self._device = "cpu"

    @property
    def name(self) -> str:
        return "lstm_autoencoder"

    @property
    def category(self) -> str:
        return "ml"

    @property
    def description(self) -> str:
        return "LSTM autoencoder detecting sequence anomalies via reconstruction error"

    def fit(
        self,
        feature_sequences: np.ndarray,
        epochs: int = None,
        learning_rate: float = 1e-3,
        batch_size: int = 32,
    ) -> Dict[str, float]:
        """
        Train the autoencoder on normal sequences.

        Args:
            feature_sequences: (n_samples, seq_length, n_features) array
            epochs: Number of training epochs
            learning_rate: Adam learning rate
            batch_size: Training batch size

        Returns:
            Training metrics dict
        """
        if not TORCH_AVAILABLE:
            logger.warning("pytorch_unavailable", msg="PyTorch not installed")
            return {"error": "PyTorch not available"}

        epochs = epochs or settings.autoencoder_epochs
        logger.info("autoencoder_training", n_samples=feature_sequences.shape[0], epochs=epochs)

        # Normalize
        reshaped = feature_sequences.reshape(-1, feature_sequences.shape[-1])
        self._mean = reshaped.mean(axis=0)
        self._std = reshaped.std(axis=0) + 1e-8
        normalized = (feature_sequences - self._mean) / self._std

        # Create model
        self._model = LSTMAutoencoder(
            input_dim=self._input_dim,
            hidden_dim=self._hidden_dim,
            latent_dim=self._latent_dim,
        ).to(self._device)

        # Create data loader
        tensor_data = torch.FloatTensor(normalized).to(self._device)
        dataset = TensorDataset(tensor_data, tensor_data)
        loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

        # Train
        optimizer = torch.optim.Adam(self._model.parameters(), lr=learning_rate)
        criterion = nn.MSELoss()

        train_losses = []
        for epoch in range(epochs):
            epoch_loss = 0.0
            self._model.train()
            for batch_x, batch_y in loader:
                optimizer.zero_grad()
                reconstruction, _ = self._model(batch_x)
                loss = criterion(reconstruction, batch_y)
                loss.backward()
                optimizer.step()
                epoch_loss += loss.item()

            avg_loss = epoch_loss / len(loader)
            train_losses.append(avg_loss)

            if (epoch + 1) % 10 == 0:
                logger.info("autoencoder_epoch", epoch=epoch + 1, loss=avg_loss)

        # Compute threshold from training data reconstruction errors
        self._model.eval()
        with torch.no_grad():
            recon, _ = self._model(tensor_data)
            errors = torch.mean((tensor_data - recon) ** 2, dim=(1, 2)).numpy()
            self._threshold = float(np.percentile(errors, self._threshold_percentile))

        self._is_fitted = True
        logger.info(
            "autoencoder_trained",
            threshold=self._threshold,
            final_loss=train_losses[-1],
        )

        return {
            "final_loss": train_losses[-1],
            "threshold": self._threshold,
            "epochs": epochs,
        }

    def add_feature_vector(self, features: Dict[str, Any]) -> None:
        """Add a feature vector to the sequence buffer."""
        vector = self._extract_features(features)
        if vector:
            self._feature_buffer.append(vector)
            if len(self._feature_buffer) > self._seq_length * 2:
                self._feature_buffer = self._feature_buffer[-self._seq_length * 2:]

    def detect(self, features: Dict[str, Any], **kwargs) -> Optional[DetectionResult]:
        """Run anomaly detection on current feature sequence."""
        if not self._is_fitted or not TORCH_AVAILABLE:
            return None

        # Add current features to buffer
        self.add_feature_vector(features)

        if len(self._feature_buffer) < self._seq_length:
            return None

        # Get most recent sequence
        sequence = self._feature_buffer[-self._seq_length:]
        seq_array = np.array([sequence], dtype=np.float32)

        # Normalize
        normalized = (seq_array - self._mean) / self._std

        # Compute reconstruction error
        self._model.eval()
        with torch.no_grad():
            tensor_input = torch.FloatTensor(normalized).to(self._device)
            reconstruction, latent = self._model(tensor_input)
            error = torch.mean((tensor_input - reconstruction) ** 2).item()

        # Compute anomaly score relative to threshold
        if self._threshold > 0:
            anomaly_score = min(1.0, error / (self._threshold * 2))
        else:
            anomaly_score = 0.0

        if anomaly_score < 0.3:
            return None

        # Identify which features had highest reconstruction error
        recon_np = reconstruction.numpy()[0]
        input_np = normalized[0]
        feature_errors = np.mean((input_np - recon_np) ** 2, axis=0)
        contributing = []
        for idx in np.argsort(feature_errors)[::-1][:3]:
            if idx < len(self._feature_names):
                contributing.append(
                    f"{self._feature_names[idx]} (error={feature_errors[idx]:.3f})"
                )

        return DetectionResult(
            event_type="anomaly",
            score=anomaly_score,
            explanation=f"LSTM autoencoder reconstruction error: {error:.4f} "
                        f"(threshold: {self._threshold:.4f}). "
                        f"Anomalous features: {', '.join(contributing)}",
            raw_features={
                "reconstruction_error": float(error),
                "threshold": float(self._threshold),
                "anomaly_score": float(anomaly_score),
            },
            detector_name=self.name,
            detector_category=self.category,
            contributing_factors=contributing,
            confidence=anomaly_score,
        )

    def _extract_features(self, features: Dict[str, Any]) -> Optional[List[float]]:
        """Extract feature vector from features dict."""
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

    def save(self, path: Optional[str] = None) -> str:
        """Save model to disk."""
        if not TORCH_AVAILABLE or self._model is None:
            return ""

        model_dir = path or settings.ml_model_dir
        os.makedirs(model_dir, exist_ok=True)

        model_path = os.path.join(model_dir, "autoencoder.pt")
        torch.save({
            "model_state_dict": self._model.state_dict(),
            "threshold": self._threshold,
            "mean": self._mean,
            "std": self._std,
            "hidden_dim": self._hidden_dim,
            "latent_dim": self._latent_dim,
            "input_dim": self._input_dim,
            "seq_length": self._seq_length,
        }, model_path)

        logger.info("autoencoder_saved", path=model_path)
        return model_path

    def load(self, path: Optional[str] = None) -> bool:
        """Load model from disk."""
        if not TORCH_AVAILABLE:
            return False

        model_dir = path or settings.ml_model_dir
        model_path = os.path.join(model_dir, "autoencoder.pt")

        if not os.path.exists(model_path):
            return False

        checkpoint = torch.load(model_path, map_location=self._device, weights_only=False)
        self._model = LSTMAutoencoder(
            input_dim=checkpoint["input_dim"],
            hidden_dim=checkpoint["hidden_dim"],
            latent_dim=checkpoint["latent_dim"],
        ).to(self._device)
        self._model.load_state_dict(checkpoint["model_state_dict"])
        self._threshold = checkpoint["threshold"]
        self._mean = checkpoint["mean"]
        self._std = checkpoint["std"]
        self._is_fitted = True

        logger.info("autoencoder_loaded", path=model_path)
        return True
