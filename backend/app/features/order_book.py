"""Order book state management and tracking."""

from collections import defaultdict
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from app.ingestion.base import MarketEvent
from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class OrderRecord:
    """Tracked individual order."""
    order_id: str
    side: str
    price: float
    quantity: float
    placed_at: datetime
    canceled_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    lifetime_ms: Optional[float] = None


class OrderBook:
    """
    Maintains local order book state from depth updates.

    Tracks:
    - Bid/ask price levels and volumes
    - Individual order placements and cancellations
    - Order lifetimes for cancel rate computation
    - Book pressure metrics
    """

    def __init__(self, symbol: str, max_levels: int = 50):
        self.symbol = symbol
        self._max_levels = max_levels
        # Price -> quantity for each side
        self._bids: Dict[float, float] = {}
        self._asks: Dict[float, float] = {}
        # Order tracking
        self._active_orders: Dict[str, OrderRecord] = {}
        self._recent_orders: List[OrderRecord] = []  # completed orders
        self._max_recent = 5000
        # Counters for feature computation
        self._place_count = 0
        self._cancel_count = 0
        self._fill_count = 0
        self._total_placed_volume = 0.0
        self._total_canceled_volume = 0.0
        self._total_filled_volume = 0.0
        # Recent events for windowed stats
        self._recent_cancels: List[datetime] = []
        self._recent_places: List[datetime] = []
        self._last_update: Optional[datetime] = None

    def process_event(self, event: MarketEvent) -> None:
        """Process a market event and update book state."""
        self._last_update = event.timestamp

        if event.event_type == "depth_update":
            self._apply_depth_update(event)
        elif event.event_type == "order_place":
            self._process_order_place(event)
        elif event.event_type == "order_cancel":
            self._process_order_cancel(event)
        elif event.event_type == "trade":
            self._process_trade(event)

    def _apply_depth_update(self, event: MarketEvent) -> None:
        """Apply incremental depth update to order book."""
        for price, qty in event.data.get("bids", []):
            price = float(price)
            qty = float(qty)
            if qty == 0:
                self._bids.pop(price, None)
            else:
                self._bids[price] = qty

        for price, qty in event.data.get("asks", []):
            price = float(price)
            qty = float(qty)
            if qty == 0:
                self._asks.pop(price, None)
            else:
                self._asks[price] = qty

        # Trim to max levels
        if len(self._bids) > self._max_levels:
            sorted_bids = sorted(self._bids.keys(), reverse=True)
            for p in sorted_bids[self._max_levels:]:
                del self._bids[p]
        if len(self._asks) > self._max_levels:
            sorted_asks = sorted(self._asks.keys())
            for p in sorted_asks[self._max_levels:]:
                del self._asks[p]

    def _process_order_place(self, event: MarketEvent) -> None:
        """Track a new order placement."""
        data = event.data
        order_id = data.get("order_id", "")
        record = OrderRecord(
            order_id=order_id,
            side=data.get("side", "bid"),
            price=float(data.get("price", 0)),
            quantity=float(data.get("quantity", 0)),
            placed_at=event.timestamp,
        )
        self._active_orders[order_id] = record
        self._place_count += 1
        self._total_placed_volume += record.quantity
        self._recent_places.append(event.timestamp)
        # Keep recent lists bounded
        if len(self._recent_places) > self._max_recent:
            self._recent_places = self._recent_places[-self._max_recent:]

    def _process_order_cancel(self, event: MarketEvent) -> None:
        """Track an order cancellation."""
        data = event.data
        order_id = data.get("order_id", "")
        self._cancel_count += 1

        record = self._active_orders.pop(order_id, None)
        if record:
            record.canceled_at = event.timestamp
            lifetime = (event.timestamp - record.placed_at).total_seconds() * 1000
            record.lifetime_ms = data.get("lifetime_ms") or lifetime
            self._total_canceled_volume += record.quantity
            self._recent_orders.append(record)
        else:
            # Order not tracked (e.g., from depth updates)
            qty = float(data.get("quantity", 0))
            self._total_canceled_volume += qty
            lifetime_ms = data.get("lifetime_ms")
            record = OrderRecord(
                order_id=order_id,
                side=data.get("side", "bid"),
                price=float(data.get("price", 0)),
                quantity=qty,
                placed_at=event.timestamp,
                canceled_at=event.timestamp,
                lifetime_ms=lifetime_ms,
            )
            self._recent_orders.append(record)

        self._recent_cancels.append(event.timestamp)
        if len(self._recent_cancels) > self._max_recent:
            self._recent_cancels = self._recent_cancels[-self._max_recent:]
        if len(self._recent_orders) > self._max_recent:
            self._recent_orders = self._recent_orders[-self._max_recent:]

    def _process_trade(self, event: MarketEvent) -> None:
        """Track a trade execution."""
        self._fill_count += 1
        qty = float(event.data.get("quantity", event.quantity or 0))
        self._total_filled_volume += qty

    @property
    def best_bid(self) -> Optional[float]:
        return max(self._bids.keys()) if self._bids else None

    @property
    def best_ask(self) -> Optional[float]:
        return min(self._asks.keys()) if self._asks else None

    @property
    def spread(self) -> Optional[float]:
        if self.best_bid and self.best_ask:
            return self.best_ask - self.best_bid
        return None

    @property
    def mid_price(self) -> Optional[float]:
        if self.best_bid and self.best_ask:
            return (self.best_bid + self.best_ask) / 2
        return None

    def get_bid_volume(self, n_levels: Optional[int] = None) -> float:
        """Total bid volume across top N price levels."""
        if not self._bids:
            return 0.0
        sorted_prices = sorted(self._bids.keys(), reverse=True)
        if n_levels:
            sorted_prices = sorted_prices[:n_levels]
        return sum(self._bids[p] for p in sorted_prices)

    def get_ask_volume(self, n_levels: Optional[int] = None) -> float:
        """Total ask volume across top N price levels."""
        if not self._asks:
            return 0.0
        sorted_prices = sorted(self._asks.keys())
        if n_levels:
            sorted_prices = sorted_prices[:n_levels]
        return sum(self._asks[p] for p in sorted_prices)

    def get_snapshot(self) -> Dict:
        """Get current order book state as a dictionary."""
        sorted_bids = sorted(self._bids.items(), key=lambda x: -x[0])[:20]
        sorted_asks = sorted(self._asks.items(), key=lambda x: x[0])[:20]
        return {
            "symbol": self.symbol,
            "bids": [[p, q] for p, q in sorted_bids],
            "asks": [[p, q] for p, q in sorted_asks],
            "best_bid": self.best_bid,
            "best_ask": self.best_ask,
            "spread": self.spread,
            "mid_price": self.mid_price,
            "bid_volume": self.get_bid_volume(),
            "ask_volume": self.get_ask_volume(),
        }

    @property
    def stats(self) -> Dict:
        """Get order book statistics."""
        return {
            "place_count": self._place_count,
            "cancel_count": self._cancel_count,
            "fill_count": self._fill_count,
            "total_placed_volume": self._total_placed_volume,
            "total_canceled_volume": self._total_canceled_volume,
            "total_filled_volume": self._total_filled_volume,
            "active_orders": len(self._active_orders),
        }

    def get_recent_orders(self, limit: int = 100) -> List[OrderRecord]:
        """Get recent completed orders."""
        return self._recent_orders[-limit:]

    def get_active_orders(self) -> Dict[str, OrderRecord]:
        """Get currently active orders."""
        return dict(self._active_orders)

    def get_depth_at_distance(self, distance_pct: float) -> Tuple[float, float]:
        """Get bid/ask volume within a percentage distance from best price."""
        bid_vol = 0.0
        ask_vol = 0.0
        if self.best_bid:
            threshold = self.best_bid * (1 - distance_pct)
            bid_vol = sum(q for p, q in self._bids.items() if p >= threshold)
        if self.best_ask:
            threshold = self.best_ask * (1 + distance_pct)
            ask_vol = sum(q for p, q in self._asks.items() if p <= threshold)
        return bid_vol, ask_vol
