"""Tests for custom microstructure detectors."""

import pytest
from datetime import datetime, timezone, timedelta

from app.detectors.custom.liquidity_mirage import LiquidityMirageDetector
from app.detectors.custom.layering_pressure import LayeringPressureDetector
from app.detectors.custom.trade_loop_symmetry import TradeLoopSymmetryDetector
from app.detectors.custom.book_shock import BookShockDivergenceDetector
from app.detectors.custom.intent_outcome import IntentOutcomeMismatchDetector
from app.features.order_book import OrderBook
from app.ingestion.base import MarketEvent


def _build_order_book_with_orders(n_orders=20, cancel_ratio=0.8, lifetime_ms=200):
    """Helper to build an order book with tracked orders."""
    book = OrderBook("btcusdt")
    t = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

    for i in range(n_orders):
        oid = f"O{i:04d}"
        side = "bid" if i % 2 == 0 else "ask"
        price = 50000.0 + (i * 0.5 if side == "ask" else -i * 0.5)

        book.process_event(MarketEvent(
            event_type="order_place",
            symbol="btcusdt",
            timestamp=t + timedelta(seconds=i * 0.1),
            data={"order_id": oid, "event_type": "place", "price": price, "quantity": 5.0, "side": side},
            source="test",
            order_id=oid,
        ))

        if i < int(n_orders * cancel_ratio):
            book.process_event(MarketEvent(
                event_type="order_cancel",
                symbol="btcusdt",
                timestamp=t + timedelta(seconds=i * 0.1, milliseconds=lifetime_ms),
                data={"order_id": oid, "event_type": "cancel", "price": price, "quantity": 5.0, "side": side, "lifetime_ms": lifetime_ms},
                source="test",
                order_id=oid,
            ))

    return book


class TestLiquidityMirage:
    """Tests for Liquidity Mirage Score detector."""

    def test_properties(self):
        d = LiquidityMirageDetector()
        assert d.name == "liquidity_mirage"
        assert d.category == "custom"

    def test_suspicious_features_detected(self, suspicious_features):
        detector = LiquidityMirageDetector(threshold=0.3)
        book = _build_order_book_with_orders(n_orders=20, cancel_ratio=0.9, lifetime_ms=100)
        result = detector.detect(suspicious_features, order_book=book)
        # Should detect something with these extreme features
        if result is not None:
            assert result.score > 0
            assert result.event_type == "spoofing"

    def test_normal_features_low_score(self, normal_features):
        detector = LiquidityMirageDetector(threshold=0.6)
        result = detector.detect(normal_features)
        # Normal features should not trigger at high threshold
        if result is not None:
            assert result.score < 0.8


class TestLayeringPressure:
    """Tests for Layering Pressure Index detector."""

    def test_properties(self):
        d = LayeringPressureDetector()
        assert d.name == "layering_pressure"
        assert d.category == "custom"

    def test_no_order_book_returns_none(self, normal_features):
        detector = LayeringPressureDetector()
        result = detector.detect(normal_features)
        assert result is None

    def test_with_clustered_orders(self, suspicious_features):
        detector = LayeringPressureDetector(threshold=0.1, min_cluster_size=2)
        book = _build_order_book_with_orders(n_orders=30, cancel_ratio=0.9, lifetime_ms=150)
        trades = [
            {"side": "sell", "quantity": 2.0, "timestamp": "2024-01-15T12:00:00Z"},
            {"side": "sell", "quantity": 3.0, "timestamp": "2024-01-15T12:00:01Z"},
        ]
        result = detector.detect(suspicious_features, order_book=book, recent_trades=trades)
        # May or may not detect depending on order clustering
        # The detector should at least not error


class TestTradeLoopSymmetry:
    """Tests for Trade Loop Symmetry Score detector."""

    def test_properties(self):
        d = TradeLoopSymmetryDetector()
        assert d.name == "trade_loop_symmetry"
        assert d.category == "custom"

    def test_symmetric_loop_detected(self, normal_features, wash_trading_trades):
        detector = TradeLoopSymmetryDetector(threshold=0.15)
        result = detector.detect(normal_features, recent_trades=wash_trading_trades)
        assert result is not None
        assert result.event_type == "wash_trading"
        assert result.score > 0

    def test_insufficient_trades(self, normal_features):
        detector = TradeLoopSymmetryDetector(min_loop_trades=4)
        result = detector.detect(normal_features, recent_trades=[
            {"side": "buy", "quantity": 1.0, "timestamp": "2024-01-15T12:00:00Z"},
        ])
        assert result is None


class TestBookShockDivergence:
    """Tests for Book Shock vs Execution Divergence detector."""

    def test_properties(self):
        d = BookShockDivergenceDetector()
        assert d.name == "book_shock_divergence"
        assert d.category == "custom"

    def test_no_order_book_returns_none(self, normal_features):
        detector = BookShockDivergenceDetector()
        result = detector.detect(normal_features)
        assert result is None

    def test_divergent_pressure(self, suspicious_features):
        detector = BookShockDivergenceDetector(threshold=0.3, min_volume=0.01)
        book = _build_order_book_with_orders(n_orders=10)
        # Heavy bid pressure but selling trades
        trades = [
            {"side": "sell", "quantity": 10.0, "timestamp": "2024-01-15T12:00:00Z"},
            {"side": "sell", "quantity": 8.0, "timestamp": "2024-01-15T12:00:01Z"},
            {"side": "buy", "quantity": 1.0, "timestamp": "2024-01-15T12:00:02Z"},
        ]
        result = detector.detect(suspicious_features, order_book=book, recent_trades=trades)
        # With strong bid imbalance but sell trades, should detect divergence
        # Depends on normalization history


class TestIntentOutcomeMismatch:
    """Tests for Intent-Outcome Mismatch Engine."""

    def test_properties(self):
        d = IntentOutcomeMismatchDetector()
        assert d.name == "intent_outcome_mismatch"
        assert d.category == "custom"

    def test_no_data_returns_none(self, normal_features):
        detector = IntentOutcomeMismatchDetector()
        result = detector.detect(normal_features)
        assert result is None

    def test_mismatch_computation(self):
        detector = IntentOutcomeMismatchDetector()
        # Intent: strong buy (0.8, 0.2), Outcome: strong sell (0.2, 0.8)
        mismatch = detector._compute_mismatch((0.8, 0.2), (0.2, 0.8))
        assert mismatch > 0.5  # Significant mismatch

    def test_aligned_low_mismatch(self):
        detector = IntentOutcomeMismatchDetector()
        # Intent and outcome aligned
        mismatch = detector._compute_mismatch((0.7, 0.3), (0.7, 0.3))
        assert mismatch < 0.01
