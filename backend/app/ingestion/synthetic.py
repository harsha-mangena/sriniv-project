"""Synthetic manipulation event generator for testing and demos."""

import asyncio
import random
import uuid
import math
from typing import AsyncIterator, List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from collections import deque

from app.ingestion.base import IngestionSource, MarketEvent
from app.utils.logger import get_logger
from app.utils.time_utils import now_utc, datetime_to_ms

logger = get_logger(__name__)


class SyntheticDataGenerator(IngestionSource):
    """
    Generates realistic synthetic market data with optional manipulation injection.

    Produces:
    - Normal trading: random walk prices, Poisson-distributed orders, realistic spreads
    - Spoofing: large orders placed far from best, canceled within 50-500ms
    - Wash trading: repeating buy-sell loops with symmetric sizes/timing
    - Layering: stepped orders across 3-5 price levels, synchronized cancellation
    - Quote stuffing: bursts of rapid order/cancel cycles
    """

    def __init__(
        self,
        symbol: str = "btcusdt",
        base_price: float = 50000.0,
        volatility: float = 0.001,
        events_per_second: float = 10.0,
        manipulation_probability: float = 0.05,
        enabled_manipulations: Optional[List[str]] = None,
    ):
        self._symbol = symbol
        self._base_price = base_price
        self._current_price = base_price
        self._volatility = volatility
        self._events_per_second = events_per_second
        self._manipulation_prob = manipulation_probability
        self._enabled_manipulations = enabled_manipulations or [
            "spoofing", "wash_trading", "layering", "quote_stuffing"
        ]
        self._connected = False
        self._order_counter = 0
        self._trade_counter = 0
        self._pending_orders: Dict[str, Dict[str, Any]] = {}

    @property
    def source_name(self) -> str:
        return "synthetic"

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        self._connected = True
        self._current_price = self._base_price
        logger.info("synthetic_started", symbol=self._symbol, base_price=self._base_price)

    async def disconnect(self) -> None:
        self._connected = False
        logger.info("synthetic_stopped")

    async def stream(self) -> AsyncIterator[MarketEvent]:
        """Generate a continuous stream of synthetic market events."""
        while self._connected:
            delay = 1.0 / self._events_per_second
            # Add Poisson-like jitter
            actual_delay = random.expovariate(1.0 / delay)
            await asyncio.sleep(min(actual_delay, 2.0))

            if not self._connected:
                return

            # Decide whether to inject manipulation
            if random.random() < self._manipulation_prob:
                manipulation = random.choice(self._enabled_manipulations)
                async for event in self._generate_manipulation(manipulation):
                    yield event
            else:
                event = self._generate_normal_event()
                yield event

    def _update_price(self) -> float:
        """Random walk price update."""
        change = random.gauss(0, self._volatility * self._current_price)
        self._current_price = max(self._current_price + change, self._current_price * 0.9)
        return self._current_price

    def _new_order_id(self) -> str:
        self._order_counter += 1
        return f"SYN-{self._order_counter:08d}"

    def _new_trade_id(self) -> str:
        self._trade_counter += 1
        return f"SYNT-{self._trade_counter:08d}"

    def _generate_normal_event(self) -> MarketEvent:
        """Generate a normal trading event (trade or order)."""
        self._update_price()
        now = now_utc()

        if random.random() < 0.4:
            # Generate a trade
            side = random.choice(["buy", "sell"])
            quantity = round(random.uniform(0.001, 1.0), 6)
            price = self._current_price * (1 + random.gauss(0, 0.0001))
            return MarketEvent(
                event_type="trade",
                symbol=self._symbol,
                timestamp=now,
                data={
                    "trade_id": self._new_trade_id(),
                    "price": round(price, 2),
                    "quantity": quantity,
                    "side": side,
                },
                source="synthetic",
                price=round(price, 2),
                quantity=quantity,
                side=side,
            )
        else:
            # Generate an order place/cancel
            side = random.choice(["bid", "ask"])
            spread_offset = random.uniform(0.01, 0.5) / 100
            if side == "bid":
                price = self._current_price * (1 - spread_offset)
            else:
                price = self._current_price * (1 + spread_offset)
            quantity = round(random.uniform(0.01, 5.0), 6)
            order_id = self._new_order_id()

            evt_type = random.choices(["place", "cancel"], weights=[0.6, 0.4])[0]
            if evt_type == "cancel" and not self._pending_orders:
                evt_type = "place"

            if evt_type == "place":
                self._pending_orders[order_id] = {
                    "price": round(price, 2),
                    "quantity": quantity,
                    "side": side,
                    "placed_at": now,
                }
            elif evt_type == "cancel" and self._pending_orders:
                order_id = random.choice(list(self._pending_orders.keys()))
                order_data = self._pending_orders.pop(order_id)
                price = order_data["price"]
                quantity = order_data["quantity"]
                side = order_data["side"]

            return MarketEvent(
                event_type=f"order_{evt_type}",
                symbol=self._symbol,
                timestamp=now,
                data={
                    "order_id": order_id,
                    "event_type": evt_type,
                    "price": round(price, 2),
                    "quantity": quantity,
                    "side": side,
                    "lifetime_ms": random.randint(100, 30000) if evt_type == "cancel" else None,
                },
                source="synthetic",
                order_id=order_id,
                price=round(price, 2),
                quantity=quantity,
                side=side,
            )

    async def _generate_manipulation(self, manipulation_type: str) -> AsyncIterator[MarketEvent]:
        """Generate a sequence of events constituting a manipulation pattern."""
        if manipulation_type == "spoofing":
            async for evt in self._generate_spoofing():
                yield evt
        elif manipulation_type == "wash_trading":
            async for evt in self._generate_wash_trading():
                yield evt
        elif manipulation_type == "layering":
            async for evt in self._generate_layering():
                yield evt
        elif manipulation_type == "quote_stuffing":
            async for evt in self._generate_quote_stuffing():
                yield evt

    async def _generate_spoofing(self) -> AsyncIterator[MarketEvent]:
        """
        Spoofing: Large orders placed far from best, canceled within 50-500ms,
        followed by opposite-side execution.
        """
        now = now_utc()
        spoof_side = random.choice(["bid", "ask"])
        exec_side = "buy" if spoof_side == "ask" else "sell"

        # Distance 0.1-0.5% from current price
        distance = random.uniform(0.001, 0.005)
        if spoof_side == "bid":
            spoof_price = self._current_price * (1 - distance)
        else:
            spoof_price = self._current_price * (1 + distance)

        # Large order size (10-50x normal)
        spoof_qty = round(random.uniform(5.0, 50.0), 4)
        order_id = self._new_order_id()

        # Place spoofing order
        yield MarketEvent(
            event_type="order_place",
            symbol=self._symbol,
            timestamp=now,
            data={
                "order_id": order_id,
                "event_type": "place",
                "price": round(spoof_price, 2),
                "quantity": spoof_qty,
                "side": spoof_side,
                "is_spoofing": True,
            },
            source="synthetic",
            order_id=order_id,
            price=round(spoof_price, 2),
            quantity=spoof_qty,
            side=spoof_side,
            metadata={"manipulation": "spoofing", "phase": "place"},
        )

        # Wait 50-500ms then cancel
        cancel_delay = random.uniform(0.05, 0.5)
        await asyncio.sleep(cancel_delay)

        cancel_time = now + timedelta(milliseconds=cancel_delay * 1000)
        yield MarketEvent(
            event_type="order_cancel",
            symbol=self._symbol,
            timestamp=cancel_time,
            data={
                "order_id": order_id,
                "event_type": "cancel",
                "price": round(spoof_price, 2),
                "quantity": spoof_qty,
                "side": spoof_side,
                "lifetime_ms": int(cancel_delay * 1000),
            },
            source="synthetic",
            order_id=order_id,
            price=round(spoof_price, 2),
            quantity=spoof_qty,
            side=spoof_side,
            metadata={"manipulation": "spoofing", "phase": "cancel"},
        )

        # Execute on opposite side
        exec_price = self._current_price * (1 + random.gauss(0, 0.0002))
        exec_qty = round(random.uniform(0.5, 5.0), 6)
        yield MarketEvent(
            event_type="trade",
            symbol=self._symbol,
            timestamp=cancel_time + timedelta(milliseconds=random.uniform(10, 100)),
            data={
                "trade_id": self._new_trade_id(),
                "price": round(exec_price, 2),
                "quantity": exec_qty,
                "side": exec_side,
            },
            source="synthetic",
            price=round(exec_price, 2),
            quantity=exec_qty,
            side=exec_side,
            metadata={"manipulation": "spoofing", "phase": "execution"},
        )

    async def _generate_wash_trading(self) -> AsyncIterator[MarketEvent]:
        """
        Wash trading: Repeating buy-sell loops with symmetric sizes and timing.
        """
        now = now_utc()
        base_qty = round(random.uniform(0.1, 2.0), 6)
        num_loops = random.randint(3, 8)
        interval_ms = random.uniform(200, 2000)

        for i in range(num_loops):
            side = "buy" if i % 2 == 0 else "sell"
            # Symmetric size with small noise
            qty = round(base_qty * (1 + random.gauss(0, 0.02)), 6)
            price = self._current_price * (1 + random.gauss(0, 0.0001))
            trade_time = now + timedelta(milliseconds=i * interval_ms)

            yield MarketEvent(
                event_type="trade",
                symbol=self._symbol,
                timestamp=trade_time,
                data={
                    "trade_id": self._new_trade_id(),
                    "price": round(price, 2),
                    "quantity": qty,
                    "side": side,
                },
                source="synthetic",
                price=round(price, 2),
                quantity=qty,
                side=side,
                metadata={"manipulation": "wash_trading", "loop_index": i},
            )
            await asyncio.sleep(interval_ms / 1000.0)

    async def _generate_layering(self) -> AsyncIterator[MarketEvent]:
        """
        Layering: Stepped orders across 3-5 price levels, synchronized cancellation.
        """
        now = now_utc()
        layer_side = random.choice(["bid", "ask"])
        num_levels = random.randint(3, 5)
        tick_size = self._current_price * 0.0001  # 1 basis point

        order_ids = []
        for level in range(num_levels):
            if layer_side == "bid":
                price = self._current_price - tick_size * (level + 2)
            else:
                price = self._current_price + tick_size * (level + 2)

            qty = round(random.uniform(1.0, 10.0), 4)
            order_id = self._new_order_id()
            order_ids.append(order_id)

            yield MarketEvent(
                event_type="order_place",
                symbol=self._symbol,
                timestamp=now + timedelta(milliseconds=level * 50),
                data={
                    "order_id": order_id,
                    "event_type": "place",
                    "price": round(price, 2),
                    "quantity": qty,
                    "side": layer_side,
                },
                source="synthetic",
                order_id=order_id,
                price=round(price, 2),
                quantity=qty,
                side=layer_side,
                metadata={"manipulation": "layering", "level": level},
            )
            await asyncio.sleep(0.05)

        # Synchronized cancellation after 200-1000ms
        cancel_delay = random.uniform(0.2, 1.0)
        await asyncio.sleep(cancel_delay)

        cancel_time = now + timedelta(seconds=cancel_delay)
        for order_id in order_ids:
            yield MarketEvent(
                event_type="order_cancel",
                symbol=self._symbol,
                timestamp=cancel_time,
                data={
                    "order_id": order_id,
                    "event_type": "cancel",
                    "price": 0,
                    "quantity": 0,
                    "side": layer_side,
                    "lifetime_ms": int(cancel_delay * 1000),
                },
                source="synthetic",
                order_id=order_id,
                side=layer_side,
                metadata={"manipulation": "layering", "phase": "cancel"},
            )

        # Opposite-side execution
        exec_side = "buy" if layer_side == "ask" else "sell"
        yield MarketEvent(
            event_type="trade",
            symbol=self._symbol,
            timestamp=cancel_time + timedelta(milliseconds=50),
            data={
                "trade_id": self._new_trade_id(),
                "price": round(self._current_price, 2),
                "quantity": round(random.uniform(1.0, 5.0), 4),
                "side": exec_side,
            },
            source="synthetic",
            price=round(self._current_price, 2),
            quantity=round(random.uniform(1.0, 5.0), 4),
            side=exec_side,
            metadata={"manipulation": "layering", "phase": "execution"},
        )

    async def _generate_quote_stuffing(self) -> AsyncIterator[MarketEvent]:
        """
        Quote stuffing: Burst of rapid order/cancel cycles (100+ per second).
        """
        now = now_utc()
        num_events = random.randint(50, 150)

        for i in range(num_events):
            order_id = self._new_order_id()
            side = random.choice(["bid", "ask"])
            price_offset = random.uniform(0.0001, 0.001)
            if side == "bid":
                price = self._current_price * (1 - price_offset)
            else:
                price = self._current_price * (1 + price_offset)
            qty = round(random.uniform(0.01, 0.5), 6)
            event_time = now + timedelta(milliseconds=i * random.uniform(5, 15))

            # Place
            yield MarketEvent(
                event_type="order_place",
                symbol=self._symbol,
                timestamp=event_time,
                data={
                    "order_id": order_id,
                    "event_type": "place",
                    "price": round(price, 2),
                    "quantity": qty,
                    "side": side,
                },
                source="synthetic",
                order_id=order_id,
                price=round(price, 2),
                quantity=qty,
                side=side,
                metadata={"manipulation": "quote_stuffing"},
            )

            # Cancel immediately (5-20ms later)
            cancel_time = event_time + timedelta(milliseconds=random.uniform(5, 20))
            yield MarketEvent(
                event_type="order_cancel",
                symbol=self._symbol,
                timestamp=cancel_time,
                data={
                    "order_id": order_id,
                    "event_type": "cancel",
                    "price": round(price, 2),
                    "quantity": qty,
                    "side": side,
                    "lifetime_ms": random.randint(5, 20),
                },
                source="synthetic",
                order_id=order_id,
                price=round(price, 2),
                quantity=qty,
                side=side,
                metadata={"manipulation": "quote_stuffing"},
            )

            if i % 10 == 0:
                await asyncio.sleep(0.001)  # Yield control periodically
