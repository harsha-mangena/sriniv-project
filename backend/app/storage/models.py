"""SQLAlchemy ORM models for market surveillance data."""

from datetime import datetime
from sqlalchemy import (
    BigInteger, String, DECIMAL, Boolean, Text, Index, Integer,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from app.storage.database import Base


class OrderBookSnapshot(Base):
    __tablename__ = "order_book_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    bids: Mapped[dict] = mapped_column(JSONB, nullable=False)
    asks: Mapped[dict] = mapped_column(JSONB, nullable=False)
    best_bid: Mapped[float] = mapped_column(DECIMAL(20, 8), nullable=True)
    best_ask: Mapped[float] = mapped_column(DECIMAL(20, 8), nullable=True)
    spread: Mapped[float] = mapped_column(DECIMAL(20, 8), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.utcnow
    )


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(String(64), nullable=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    side: Mapped[str] = mapped_column(String(4), nullable=False)
    price: Mapped[float] = mapped_column(DECIMAL(20, 8), nullable=False)
    quantity: Mapped[float] = mapped_column(DECIMAL(20, 8), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)
    lifetime_ms: Mapped[int] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.utcnow
    )

    __table_args__ = (
        Index("idx_orders_symbol_time", "symbol", "timestamp"),
    )


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trade_id: Mapped[str] = mapped_column(String(64), nullable=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    price: Mapped[float] = mapped_column(DECIMAL(20, 8), nullable=False)
    quantity: Mapped[float] = mapped_column(DECIMAL(20, 8), nullable=False)
    side: Mapped[str] = mapped_column(String(4), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    buyer_id: Mapped[str] = mapped_column(String(64), nullable=True)
    seller_id: Mapped[str] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.utcnow
    )

    __table_args__ = (
        Index("idx_trades_symbol_time", "symbol", "timestamp"),
    )


class Feature(Base):
    __tablename__ = "features"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    window_start: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    cancel_rate: Mapped[float] = mapped_column(DECIMAL(10, 6), nullable=True)
    order_to_trade_ratio: Mapped[float] = mapped_column(DECIMAL(10, 6), nullable=True)
    bid_ask_imbalance: Mapped[float] = mapped_column(DECIMAL(10, 6), nullable=True)
    depth_concentration: Mapped[float] = mapped_column(DECIMAL(10, 6), nullable=True)
    order_arrival_burstiness: Mapped[float] = mapped_column(DECIMAL(10, 6), nullable=True)
    avg_order_lifetime_ms: Mapped[float] = mapped_column(DECIMAL(10, 2), nullable=True)
    volume_entropy: Mapped[float] = mapped_column(DECIMAL(10, 6), nullable=True)
    rolling_zscore_volume: Mapped[float] = mapped_column(DECIMAL(10, 6), nullable=True)
    rolling_zscore_cancel: Mapped[float] = mapped_column(DECIMAL(10, 6), nullable=True)
    raw_features: Mapped[dict] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.utcnow
    )


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence_score: Mapped[float] = mapped_column(DECIMAL(5, 2), nullable=False)
    rule_scores: Mapped[dict] = mapped_column(JSONB, nullable=True)
    ml_scores: Mapped[dict] = mapped_column(JSONB, nullable=True)
    custom_scores: Mapped[dict] = mapped_column(JSONB, nullable=True)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    contributing_features: Mapped[dict] = mapped_column(JSONB, nullable=True)
    raw_evidence: Mapped[dict] = mapped_column(JSONB, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.utcnow
    )

    __table_args__ = (
        Index("idx_alerts_symbol", "symbol"),
        Index("idx_alerts_timestamp", "timestamp"),
        Index("idx_alerts_type", "alert_type"),
        Index("idx_alerts_severity", "severity"),
    )
