"""Shared test fixtures for the surveillance platform."""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

from app.ingestion.base import MarketEvent
from app.features.feature_engine import FeatureEngine
from app.features.order_book import OrderBook
from app.scoring.engine import ScoringEngine


@pytest.fixture
def feature_engine():
    """Fresh feature engine instance."""
    return FeatureEngine(window_seconds=60, rolling_size=50)


@pytest.fixture
def order_book():
    """Fresh order book instance."""
    return OrderBook("btcusdt")


@pytest.fixture
def scoring_engine():
    """Fresh scoring engine instance."""
    return ScoringEngine()


@pytest.fixture
def sample_timestamp():
    """Sample UTC timestamp."""
    return datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def normal_trade_event(sample_timestamp):
    """Normal trade event."""
    return MarketEvent(
        event_type="trade",
        symbol="btcusdt",
        timestamp=sample_timestamp,
        data={
            "trade_id": "T001",
            "price": 50000.0,
            "quantity": 0.5,
            "side": "buy",
        },
        source="test",
        price=50000.0,
        quantity=0.5,
        side="buy",
    )


@pytest.fixture
def order_place_event(sample_timestamp):
    """Order place event."""
    return MarketEvent(
        event_type="order_place",
        symbol="btcusdt",
        timestamp=sample_timestamp,
        data={
            "order_id": "O001",
            "event_type": "place",
            "price": 49950.0,
            "quantity": 10.0,
            "side": "bid",
        },
        source="test",
        order_id="O001",
        price=49950.0,
        quantity=10.0,
        side="bid",
    )


@pytest.fixture
def order_cancel_event(sample_timestamp):
    """Order cancel event with short lifetime."""
    return MarketEvent(
        event_type="order_cancel",
        symbol="btcusdt",
        timestamp=sample_timestamp + timedelta(milliseconds=200),
        data={
            "order_id": "O001",
            "event_type": "cancel",
            "price": 49950.0,
            "quantity": 10.0,
            "side": "bid",
            "lifetime_ms": 200,
        },
        source="test",
        order_id="O001",
        price=49950.0,
        quantity=10.0,
        side="bid",
    )


@pytest.fixture
def depth_update_event(sample_timestamp):
    """Depth update event."""
    return MarketEvent(
        event_type="depth_update",
        symbol="btcusdt",
        timestamp=sample_timestamp,
        data={
            "bids": [[49990.0, 1.5], [49980.0, 2.0], [49970.0, 3.0]],
            "asks": [[50010.0, 1.0], [50020.0, 1.5], [50030.0, 2.5]],
        },
        source="test",
    )


@pytest.fixture
def spoofing_events(sample_timestamp) -> List[MarketEvent]:
    """Sequence of events simulating spoofing."""
    events = []
    t = sample_timestamp

    # Normal trades first
    for i in range(10):
        events.append(MarketEvent(
            event_type="trade",
            symbol="btcusdt",
            timestamp=t + timedelta(seconds=i),
            data={"trade_id": f"T{i}", "price": 50000.0, "quantity": 0.1, "side": "buy"},
            source="test",
            price=50000.0,
            quantity=0.1,
            side="buy",
        ))

    # Large spoofing orders
    for i in range(20):
        oid = f"SPOOF-{i}"
        place_time = t + timedelta(seconds=10 + i * 0.5)
        events.append(MarketEvent(
            event_type="order_place",
            symbol="btcusdt",
            timestamp=place_time,
            data={"order_id": oid, "event_type": "place", "price": 49900.0, "quantity": 50.0, "side": "bid"},
            source="test",
            order_id=oid,
            price=49900.0,
            quantity=50.0,
            side="bid",
        ))
        # Cancel after 100-300ms
        cancel_time = place_time + timedelta(milliseconds=200)
        events.append(MarketEvent(
            event_type="order_cancel",
            symbol="btcusdt",
            timestamp=cancel_time,
            data={"order_id": oid, "event_type": "cancel", "price": 49900.0, "quantity": 50.0, "side": "bid", "lifetime_ms": 200},
            source="test",
            order_id=oid,
            price=49900.0,
            quantity=50.0,
            side="bid",
        ))

    return events


@pytest.fixture
def wash_trading_trades(sample_timestamp) -> List[Dict[str, Any]]:
    """Recent trades representing wash trading pattern."""
    trades = []
    base_qty = 1.0
    interval = 1.0

    for i in range(20):
        side = "buy" if i % 2 == 0 else "sell"
        ts = sample_timestamp + timedelta(seconds=i * interval)
        trades.append({
            "timestamp": ts.isoformat(),
            "price": 50000.0 + (i % 3),
            "quantity": base_qty * (1 + 0.01 * (i % 3)),
            "side": side,
            "trade_id": f"WT-{i}",
        })

    return trades


@pytest.fixture
def normal_features() -> Dict[str, Any]:
    """Normal market features (not suspicious)."""
    return {
        "symbol": "btcusdt",
        "window_start": "2024-01-15T12:00:00+00:00",
        "window_end": "2024-01-15T12:01:00+00:00",
        "cancel_rate": 0.15,
        "order_to_trade_ratio": 3.0,
        "bid_ask_imbalance": 0.05,
        "depth_concentration": 0.3,
        "order_arrival_burstiness": 0.1,
        "avg_order_lifetime_ms": 5000.0,
        "volume_entropy": 2.5,
        "rolling_zscore_volume": 0.3,
        "rolling_zscore_cancel": 0.2,
        "bid_volume": 100.0,
        "ask_volume": 95.0,
        "total_orders": 50,
        "total_trades": 20,
        "total_cancels": 8,
        "best_bid": 49990.0,
        "best_ask": 50010.0,
        "spread": 20.0,
        "mid_price": 50000.0,
        "order_rate": 1.0,
    }


@pytest.fixture
def suspicious_features() -> Dict[str, Any]:
    """Suspicious market features (likely manipulation)."""
    return {
        "symbol": "btcusdt",
        "window_start": "2024-01-15T12:00:00+00:00",
        "window_end": "2024-01-15T12:01:00+00:00",
        "cancel_rate": 0.85,
        "order_to_trade_ratio": 25.0,
        "bid_ask_imbalance": 0.7,
        "depth_concentration": 0.8,
        "order_arrival_burstiness": 0.8,
        "avg_order_lifetime_ms": 150.0,
        "volume_entropy": 0.5,
        "rolling_zscore_volume": 3.5,
        "rolling_zscore_cancel": 4.0,
        "bid_volume": 500.0,
        "ask_volume": 50.0,
        "total_orders": 200,
        "total_trades": 8,
        "total_cancels": 170,
        "best_bid": 49990.0,
        "best_ask": 50010.0,
        "spread": 20.0,
        "mid_price": 50000.0,
        "order_rate": 50.0,
    }
