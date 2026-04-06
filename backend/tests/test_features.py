"""Unit tests for feature engineering."""

import pytest
from datetime import datetime, timezone, timedelta

from app.features.order_book import OrderBook
from app.features.feature_engine import FeatureEngine
from app.features.rolling_stats import RollingWindow, RollingEntropy, BurstinessDetector
from app.ingestion.base import MarketEvent


class TestRollingWindow:
    """Tests for RollingWindow statistics."""

    def test_basic_stats(self):
        rw = RollingWindow(window_size=10)
        for v in [1.0, 2.0, 3.0, 4.0, 5.0]:
            rw.update(v)
        stats = rw.stats
        assert stats.count == 5
        assert abs(stats.mean - 3.0) < 0.01
        assert stats.min_val == 1.0
        assert stats.max_val == 5.0

    def test_sliding_window(self):
        rw = RollingWindow(window_size=3)
        for v in [1.0, 2.0, 3.0, 4.0, 5.0]:
            rw.update(v)
        stats = rw.stats
        assert stats.count == 3
        assert abs(stats.mean - 4.0) < 0.01

    def test_zscore(self):
        rw = RollingWindow(window_size=100)
        for i in range(50):
            rw.update(10.0)
        rw.update(20.0)
        assert rw.current_zscore > 2.0

    def test_reset(self):
        rw = RollingWindow(window_size=10)
        rw.update(5.0)
        rw.reset()
        assert rw.stats.count == 0


class TestRollingEntropy:
    """Tests for RollingEntropy."""

    def test_uniform_entropy(self):
        re = RollingEntropy(window_size=100, num_bins=10)
        for i in range(100):
            # Use values that distribute across bins
            re.update(float(i) * 0.1)
        assert re.entropy > 1.0  # High entropy for diverse values

    def test_constant_entropy(self):
        re = RollingEntropy(window_size=50, num_bins=10)
        for _ in range(50):
            re.update(5.0)
        assert re.entropy < 0.5  # Low entropy for constant


class TestBurstinessDetector:
    """Tests for BurstinessDetector."""

    def test_periodic_not_bursty(self):
        bd = BurstinessDetector(window_size=20)
        for i in range(20):
            bd.add_event(i * 1000.0)
        assert bd.burstiness < 0.2

    def test_bursty_events(self):
        bd = BurstinessDetector(window_size=30)
        # Cluster of events then gap
        for i in range(10):
            bd.add_event(i * 10.0)
        for i in range(10):
            bd.add_event(5000.0 + i * 10.0)
        for i in range(10):
            bd.add_event(10000.0 + i * 10.0)
        assert bd.burstiness > 0.3

    def test_event_rate(self):
        bd = BurstinessDetector(window_size=20)
        for i in range(10):
            bd.add_event(i * 100.0)
        rate = bd.event_rate
        assert rate > 5.0  # ~10 events per second


class TestOrderBook:
    """Tests for OrderBook state management."""

    def test_depth_update(self, order_book, depth_update_event):
        order_book.process_event(depth_update_event)
        assert order_book.best_bid == 49990.0
        assert order_book.best_ask == 50010.0
        assert order_book.spread == 20.0

    def test_order_tracking(self, order_book, order_place_event, order_cancel_event):
        order_book.process_event(order_place_event)
        assert len(order_book.get_active_orders()) == 1
        order_book.process_event(order_cancel_event)
        assert len(order_book.get_active_orders()) == 0
        recent = order_book.get_recent_orders()
        assert len(recent) == 1
        assert recent[0].lifetime_ms == 200

    def test_trade_counting(self, order_book, normal_trade_event):
        order_book.process_event(normal_trade_event)
        stats = order_book.stats
        assert stats["fill_count"] == 1

    def test_volume_calculation(self, order_book, depth_update_event):
        order_book.process_event(depth_update_event)
        bid_vol = order_book.get_bid_volume(n_levels=2)
        assert bid_vol == 3.5  # 1.5 + 2.0
        ask_vol = order_book.get_ask_volume(n_levels=2)
        assert ask_vol == 2.5  # 1.0 + 1.5


class TestFeatureEngine:
    """Tests for FeatureEngine."""

    def test_process_trade(self, feature_engine, normal_trade_event):
        features = feature_engine.process_event(normal_trade_event)
        assert features is not None
        assert features["symbol"] == "btcusdt"
        assert "cancel_rate" in features
        assert "order_to_trade_ratio" in features

    def test_cancel_rate_computation(self, feature_engine):
        from app.utils.time_utils import now_utc
        now = now_utc()
        # Place and cancel several orders with recent timestamps
        for i in range(10):
            t = now - timedelta(seconds=30) + timedelta(seconds=i)
            feature_engine.process_event(MarketEvent(
                event_type="order_place",
                symbol="btcusdt",
                timestamp=t,
                data={"order_id": f"O{i}", "event_type": "place", "price": 50000.0, "quantity": 1.0, "side": "bid"},
                source="test",
            ))
            if i < 7:  # Cancel 7 out of 10
                feature_engine.process_event(MarketEvent(
                    event_type="order_cancel",
                    symbol="btcusdt",
                    timestamp=t + timedelta(milliseconds=100),
                    data={"order_id": f"O{i}", "event_type": "cancel", "price": 50000.0, "quantity": 1.0, "side": "bid", "lifetime_ms": 100},
                    source="test",
                ))

        features = feature_engine.compute_features("btcusdt")
        # Should have non-zero cancel rate
        assert features["cancel_rate"] > 0

    def test_feature_vector(self, feature_engine, normal_trade_event):
        feature_engine.process_event(normal_trade_event)
        vector = feature_engine.get_feature_vector("btcusdt")
        assert len(vector) == 9
        assert all(isinstance(v, float) for v in vector)

    def test_feature_names(self):
        names = FeatureEngine.feature_names()
        assert len(names) == 9
        assert "cancel_rate" in names
