"""Application configuration via Pydantic settings."""

from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://surveillance:surveillance@localhost:5432/market_surveillance"
    sync_database_url: str = "postgresql://surveillance:surveillance@localhost:5432/market_surveillance"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = True
    log_level: str = "INFO"

    # Binance
    binance_ws_url: str = "wss://stream.binance.com:9443/ws"
    default_symbols: str = "btcusdt,ethusdt"

    # Scoring weights
    weight_rule: float = 0.35
    weight_ml: float = 0.30
    weight_custom: float = 0.35

    # ML
    ml_model_dir: str = "models"
    isolation_forest_contamination: float = 0.05
    autoencoder_epochs: int = 50
    autoencoder_hidden_dim: int = 32
    autoencoder_latent_dim: int = 16

    # Feature windows
    feature_window_seconds: int = 60
    rolling_window_size: int = 100

    @property
    def symbols_list(self) -> List[str]:
        return [s.strip().lower() for s in self.default_symbols.split(",")]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
