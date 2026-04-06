"""Pydantic request/response models for the API."""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


# --- Alert Schemas ---

class AlertResponse(BaseModel):
    id: Optional[int] = None
    symbol: str
    alert_type: str
    severity: str
    confidence_score: float
    rule_scores: Optional[Dict[str, float]] = None
    ml_scores: Optional[Dict[str, float]] = None
    custom_scores: Optional[Dict[str, float]] = None
    explanation: str
    contributing_features: Optional[Dict[str, Any]] = None
    raw_evidence: Optional[Dict[str, Any]] = None
    timestamp: str
    resolved: bool = False
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class AlertListResponse(BaseModel):
    alerts: List[AlertResponse]
    total: int
    page: int = 1
    page_size: int = 50


class AlertFilterParams(BaseModel):
    symbol: Optional[str] = None
    alert_type: Optional[str] = None
    severity: Optional[str] = None
    min_confidence: Optional[float] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    resolved: Optional[bool] = None
    page: int = 1
    page_size: int = 50


# --- Order Book Schemas ---

class OrderBookLevel(BaseModel):
    price: float
    quantity: float


class OrderBookResponse(BaseModel):
    symbol: str
    bids: List[List[float]]
    asks: List[List[float]]
    best_bid: Optional[float] = None
    best_ask: Optional[float] = None
    spread: Optional[float] = None
    mid_price: Optional[float] = None
    bid_volume: float = 0.0
    ask_volume: float = 0.0


# --- Trade Schemas ---

class TradeResponse(BaseModel):
    timestamp: str
    price: float
    quantity: float
    side: str
    trade_id: str = ""


class TradeListResponse(BaseModel):
    trades: List[TradeResponse]
    symbol: str
    count: int


# --- Feature Schemas ---

class FeatureResponse(BaseModel):
    symbol: str
    window_start: str
    window_end: str
    cancel_rate: float = 0.0
    order_to_trade_ratio: float = 0.0
    bid_ask_imbalance: float = 0.0
    depth_concentration: float = 0.0
    order_arrival_burstiness: float = 0.0
    avg_order_lifetime_ms: float = 0.0
    volume_entropy: float = 0.0
    rolling_zscore_volume: float = 0.0
    rolling_zscore_cancel: float = 0.0
    bid_volume: float = 0.0
    ask_volume: float = 0.0
    total_orders: int = 0
    total_trades: int = 0
    total_cancels: int = 0
    best_bid: Optional[float] = None
    best_ask: Optional[float] = None
    spread: Optional[float] = None
    mid_price: Optional[float] = None
    order_rate: float = 0.0


# --- Replay Schemas ---

class ReplayStartRequest(BaseModel):
    scenario: str = Field(..., description="Scenario type: normal, spoofing, wash_trading, layering, quote_stuffing")
    symbol: str = "btcusdt"
    speed: float = Field(1.0, ge=0.1, le=100.0)
    n_events: int = Field(50, ge=1, le=1000)


class ReplayInjectRequest(BaseModel):
    event_type: str = Field(..., description="Event type to inject: spoofing, wash_trading, layering, quote_stuffing")
    symbol: str = "btcusdt"


class ReplayStatusResponse(BaseModel):
    running: bool
    scenario: Optional[str] = None
    events_processed: int = 0


# --- Stats Schemas ---

class DashboardStats(BaseModel):
    total_alerts: int = 0
    critical_alerts: int = 0
    high_alerts: int = 0
    medium_alerts: int = 0
    low_alerts: int = 0
    active_symbols: List[str] = []
    events_processed: int = 0
    alerts_by_type: Dict[str, int] = {}
    replay_status: Optional[ReplayStatusResponse] = None
    uptime_seconds: float = 0.0


# --- Health Check ---

class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str = "1.0.0"
    database: str = "unknown"
    redis: str = "unknown"
    ingestion: str = "unknown"
