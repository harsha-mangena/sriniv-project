"""Feature extraction pipeline for market surveillance."""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from collections import deque

from app.features.order_book import OrderBook
from app.features.rolling_stats import RollingWindow, RollingEntropy, BurstinessDetector
from app.ingestion.base import MarketEvent
from app.config import settings
from app.utils.logger import get_logger
from app.utils.time_utils import now_utc, datetime_to_ms

logger = get_logger(__name__)


class FeatureEngine:
    """
    Extracts surveillance features from order book state and market events.

    Computes per-symbol features:
    - cancel_rate: canceled orders / total orders in window
    - order_to_trade_ratio: orders placed / trades executed
    - bid_ask_imbalance: (bid_vol - ask_vol) / (bid_vol + ask_vol)
    - depth_concentration: top-3 level volume / total volume
    - order_arrival_burstiness: CV-based burstiness of order arrivals
    - avg_order_lifetime_ms: mean lifetime of canceled orders
    - volume_entropy: Shannon entropy of trade volume distribution
    - rolling_zscore_volume: z-score of recent trade volume
    - rolling_zscore_cancel: z-score of cancel rate
    """

    def __init__(self, window_seconds: int = None, rolling_size: int = None):
        self._window_seconds = window_seconds or settings.feature_window_seconds
        self._rolling_size = rolling_size or settings.rolling_window_size

        # Per-symbol state
        self._order_books: Dict[str, OrderBook] = {}
        self._volume_windows: Dict[str, RollingWindow] = {}
        self._cancel_rate_windows: Dict[str, RollingWindow] = {}
        self._volume_entropy: Dict[str, RollingEntropy] = {}
        self._burstiness_detectors: Dict[str, BurstinessDetector] = {}

        # Per-symbol event buffers for windowed computation
        self._trade_buffer: Dict[str, deque] = {}
        self._order_buffer: Dict[str, deque] = {}
        self._cancel_buffer: Dict[str, deque] = {}

    def _ensure_symbol(self, symbol: str) -> None:
        """Initialize tracking structures for a new symbol."""
        if symbol not in self._order_books:
            self._order_books[symbol] = OrderBook(symbol)
            self._volume_windows[symbol] = RollingWindow(self._rolling_size)
            self._cancel_rate_windows[symbol] = RollingWindow(self._rolling_size)
            self._volume_entropy[symbol] = RollingEntropy(self._rolling_size)
            self._burstiness_detectors[symbol] = BurstinessDetector(self._rolling_size)
            self._trade_buffer[symbol] = deque(maxlen=5000)
            self._order_buffer[symbol] = deque(maxlen=5000)
            self._cancel_buffer[symbol] = deque(maxlen=5000)

    def process_event(self, event: MarketEvent) -> Optional[Dict[str, Any]]:
        """
        Process a market event, update state, and return computed features.

        Returns features dict if enough data is available, None otherwise.
        """
        symbol = event.symbol
        self._ensure_symbol(symbol)

        # Update order book
        book = self._order_books[symbol]
        book.process_event(event)

        ts_ms = datetime_to_ms(event.timestamp)

        # Buffer events by type
        if event.event_type == "trade":
            self._trade_buffer[symbol].append(event)
            vol = event.quantity or event.data.get("quantity", 0)
            self._volume_windows[symbol].update(float(vol))
            self._volume_entropy[symbol].update(float(vol))
        elif event.event_type in ("order_place", "order_cancel", "order_modify"):
            self._order_buffer[symbol].append(event)
            self._burstiness_detectors[symbol].add_event(ts_ms)
            if event.event_type == "order_cancel":
                self._cancel_buffer[symbol].append(event)

        return self.compute_features(symbol)

    def compute_features(self, symbol: str) -> Dict[str, Any]:
        """Compute all features for a symbol from current state."""
        self._ensure_symbol(symbol)
        book = self._order_books[symbol]
        now = now_utc()
        window_start = now - timedelta(seconds=self._window_seconds)

        # Filter buffered events to window
        window_trades = [e for e in self._trade_buffer[symbol]
                         if e.timestamp >= window_start]
        window_orders = [e for e in self._order_buffer[symbol]
                         if e.timestamp >= window_start]
        window_cancels = [e for e in self._cancel_buffer[symbol]
                          if e.timestamp >= window_start]

        # Cancel rate
        total_orders = len(window_orders)
        num_cancels = len(window_cancels)
        cancel_rate = num_cancels / total_orders if total_orders > 0 else 0.0
        self._cancel_rate_windows[symbol].update(cancel_rate)

        # Order-to-trade ratio
        num_trades = len(window_trades)
        order_to_trade = total_orders / num_trades if num_trades > 0 else 0.0

        # Bid-ask imbalance
        bid_vol = book.get_bid_volume(n_levels=10)
        ask_vol = book.get_ask_volume(n_levels=10)
        total_vol = bid_vol + ask_vol
        bid_ask_imbalance = (bid_vol - ask_vol) / total_vol if total_vol > 0 else 0.0

        # Depth concentration (top-3 vs total)
        top3_bid = book.get_bid_volume(n_levels=3)
        top3_ask = book.get_ask_volume(n_levels=3)
        total_bid = book.get_bid_volume()
        total_ask = book.get_ask_volume()
        total_depth = total_bid + total_ask
        top3_depth = top3_bid + top3_ask
        depth_concentration = top3_depth / total_depth if total_depth > 0 else 0.0

        # Order arrival burstiness
        burstiness = self._burstiness_detectors[symbol].burstiness

        # Average order lifetime
        lifetimes = []
        for order in book.get_recent_orders(100):
            if order.lifetime_ms is not None:
                lifetimes.append(order.lifetime_ms)
        avg_lifetime = sum(lifetimes) / len(lifetimes) if lifetimes else 0.0

        # Volume entropy
        vol_entropy = self._volume_entropy[symbol].entropy

        # Rolling z-scores
        vol_zscore = self._volume_windows[symbol].current_zscore
        cancel_zscore = self._cancel_rate_windows[symbol].current_zscore

        features = {
            "symbol": symbol,
            "window_start": window_start.isoformat(),
            "window_end": now.isoformat(),
            "cancel_rate": round(cancel_rate, 6),
            "order_to_trade_ratio": round(order_to_trade, 6),
            "bid_ask_imbalance": round(bid_ask_imbalance, 6),
            "depth_concentration": round(depth_concentration, 6),
            "order_arrival_burstiness": round(burstiness, 6),
            "avg_order_lifetime_ms": round(avg_lifetime, 2),
            "volume_entropy": round(vol_entropy, 6),
            "rolling_zscore_volume": round(vol_zscore, 6),
            "rolling_zscore_cancel": round(cancel_zscore, 6),
            # Additional raw features for detectors
            "bid_volume": bid_vol,
            "ask_volume": ask_vol,
            "total_orders": total_orders,
            "total_trades": num_trades,
            "total_cancels": num_cancels,
            "best_bid": book.best_bid,
            "best_ask": book.best_ask,
            "spread": book.spread,
            "mid_price": book.mid_price,
            "order_rate": self._burstiness_detectors[symbol].event_rate,
        }

        return features

    def get_order_book(self, symbol: str) -> Optional[OrderBook]:
        """Get the order book for a symbol."""
        return self._order_books.get(symbol)

    def get_feature_vector(self, symbol: str) -> List[float]:
        """Get features as a numeric vector for ML models."""
        features = self.compute_features(symbol)
        return [
            features["cancel_rate"],
            features["order_to_trade_ratio"],
            features["bid_ask_imbalance"],
            features["depth_concentration"],
            features["order_arrival_burstiness"],
            features["avg_order_lifetime_ms"],
            features["volume_entropy"],
            features["rolling_zscore_volume"],
            features["rolling_zscore_cancel"],
        ]

    @staticmethod
    def feature_names() -> List[str]:
        return [
            "cancel_rate",
            "order_to_trade_ratio",
            "bid_ask_imbalance",
            "depth_concentration",
            "order_arrival_burstiness",
            "avg_order_lifetime_ms",
            "volume_entropy",
            "rolling_zscore_volume",
            "rolling_zscore_cancel",
        ]

    def get_recent_trades(self, symbol: str, limit: int = 50) -> List[Dict]:
        """Get recent trades for a symbol."""
        if symbol not in self._trade_buffer:
            return []
        trades = list(self._trade_buffer[symbol])[-limit:]
        return [
            {
                "timestamp": e.timestamp.isoformat(),
                "price": e.data.get("price", e.price),
                "quantity": e.data.get("quantity", e.quantity),
                "side": e.data.get("side", e.side),
                "trade_id": e.data.get("trade_id", ""),
            }
            for e in trades
        ]
