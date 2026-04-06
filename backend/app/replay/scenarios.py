"""Pre-built manipulation scenarios for replay and testing."""

from typing import List, Dict, Any
from datetime import datetime, timezone, timedelta
import random

from app.utils.time_utils import now_utc, datetime_to_ms


def generate_normal_trades(
    n_trades: int = 100,
    symbol: str = "btcusdt",
    base_price: float = 50000.0,
    start_time: datetime = None,
) -> List[Dict[str, Any]]:
    """Generate normal trading activity."""
    start = start_time or now_utc()
    trades = []
    price = base_price

    for i in range(n_trades):
        price += random.gauss(0, base_price * 0.0005)
        side = random.choice(["buy", "sell"])
        quantity = round(random.uniform(0.001, 2.0), 6)
        timestamp = start + timedelta(milliseconds=i * random.uniform(100, 5000))

        trades.append({
            "timestamp_ms": datetime_to_ms(timestamp),
            "timestamp": timestamp.isoformat(),
            "symbol": symbol,
            "side": side,
            "price": round(price, 2),
            "quantity": quantity,
            "trade_id": f"NORM-{i:06d}",
        })

    return trades


def generate_spoofing_scenario(
    n_events: int = 50,
    symbol: str = "btcusdt",
    base_price: float = 50000.0,
    start_time: datetime = None,
) -> List[Dict[str, Any]]:
    """
    Generate a spoofing scenario.

    Pattern: Large bid orders placed far from best, canceled within 50-500ms,
    followed by sell execution.
    """
    start = start_time or now_utc()
    events = []
    price = base_price
    t = start

    for i in range(n_events):
        # Normal activity
        for _ in range(random.randint(3, 8)):
            t += timedelta(milliseconds=random.uniform(200, 2000))
            side = random.choice(["buy", "sell"])
            events.append({
                "timestamp_ms": datetime_to_ms(t),
                "timestamp": t.isoformat(),
                "symbol": symbol,
                "event_type": "trade",
                "side": side,
                "price": round(price + random.gauss(0, 10), 2),
                "quantity": round(random.uniform(0.01, 1.0), 6),
                "trade_id": f"SP-T-{len(events):06d}",
            })

        # Spoofing sequence
        spoof_price = round(price - random.uniform(20, 100), 2)
        spoof_qty = round(random.uniform(10.0, 50.0), 4)
        order_id = f"SP-O-{i:06d}"

        # Place large bid
        t += timedelta(milliseconds=50)
        events.append({
            "timestamp_ms": datetime_to_ms(t),
            "timestamp": t.isoformat(),
            "symbol": symbol,
            "event_type": "place",
            "side": "bid",
            "price": spoof_price,
            "quantity": spoof_qty,
            "order_id": order_id,
        })

        # Cancel after 50-500ms
        cancel_delay = random.uniform(50, 500)
        t += timedelta(milliseconds=cancel_delay)
        events.append({
            "timestamp_ms": datetime_to_ms(t),
            "timestamp": t.isoformat(),
            "symbol": symbol,
            "event_type": "cancel",
            "side": "bid",
            "price": spoof_price,
            "quantity": spoof_qty,
            "order_id": order_id,
            "lifetime_ms": int(cancel_delay),
        })

        # Sell execution shortly after
        t += timedelta(milliseconds=random.uniform(10, 100))
        events.append({
            "timestamp_ms": datetime_to_ms(t),
            "timestamp": t.isoformat(),
            "symbol": symbol,
            "event_type": "trade",
            "side": "sell",
            "price": round(price - random.uniform(1, 5), 2),
            "quantity": round(random.uniform(1.0, 5.0), 4),
            "trade_id": f"SP-EX-{i:06d}",
        })

        price += random.gauss(0, 5)

    return events


def generate_wash_trading_scenario(
    n_loops: int = 20,
    symbol: str = "btcusdt",
    base_price: float = 50000.0,
    start_time: datetime = None,
) -> List[Dict[str, Any]]:
    """
    Generate a wash trading scenario.

    Pattern: Repeating buy-sell loops with symmetric sizes and timing.
    """
    start = start_time or now_utc()
    events = []
    price = base_price
    t = start
    base_qty = round(random.uniform(0.5, 2.0), 4)
    interval_ms = random.uniform(500, 2000)

    for loop in range(n_loops):
        # Normal noise trades
        for _ in range(random.randint(1, 3)):
            t += timedelta(milliseconds=random.uniform(1000, 5000))
            events.append({
                "timestamp_ms": datetime_to_ms(t),
                "timestamp": t.isoformat(),
                "symbol": symbol,
                "event_type": "trade",
                "side": random.choice(["buy", "sell"]),
                "price": round(price + random.gauss(0, 5), 2),
                "quantity": round(random.uniform(0.01, 0.5), 6),
                "trade_id": f"WT-N-{len(events):06d}",
            })

        # Wash trading loop (buy-sell pair)
        wash_qty = round(base_qty * (1 + random.gauss(0, 0.02)), 4)
        wash_price = round(price + random.gauss(0, 2), 2)

        # Buy
        t += timedelta(milliseconds=interval_ms * (1 + random.gauss(0, 0.05)))
        events.append({
            "timestamp_ms": datetime_to_ms(t),
            "timestamp": t.isoformat(),
            "symbol": symbol,
            "event_type": "trade",
            "side": "buy",
            "price": wash_price,
            "quantity": wash_qty,
            "trade_id": f"WT-B-{loop:06d}",
        })

        # Sell (symmetric)
        t += timedelta(milliseconds=interval_ms * (1 + random.gauss(0, 0.05)))
        events.append({
            "timestamp_ms": datetime_to_ms(t),
            "timestamp": t.isoformat(),
            "symbol": symbol,
            "event_type": "trade",
            "side": "sell",
            "price": round(wash_price + random.gauss(0, 0.5), 2),
            "quantity": round(wash_qty * (1 + random.gauss(0, 0.01)), 4),
            "trade_id": f"WT-S-{loop:06d}",
        })

        price += random.gauss(0, 2)

    return events


def generate_layering_scenario(
    n_episodes: int = 10,
    symbol: str = "btcusdt",
    base_price: float = 50000.0,
    start_time: datetime = None,
) -> List[Dict[str, Any]]:
    """
    Generate a layering scenario.

    Pattern: Stepped orders across 3-5 levels, synchronized cancellation,
    then opposite-side execution.
    """
    start = start_time or now_utc()
    events = []
    price = base_price
    t = start

    for ep in range(n_episodes):
        # Normal activity
        for _ in range(random.randint(5, 10)):
            t += timedelta(milliseconds=random.uniform(200, 2000))
            events.append({
                "timestamp_ms": datetime_to_ms(t),
                "timestamp": t.isoformat(),
                "symbol": symbol,
                "event_type": "trade",
                "side": random.choice(["buy", "sell"]),
                "price": round(price + random.gauss(0, 10), 2),
                "quantity": round(random.uniform(0.01, 1.0), 6),
                "trade_id": f"LY-T-{len(events):06d}",
            })

        # Layering: place orders at multiple levels
        layer_side = random.choice(["bid", "ask"])
        num_levels = random.randint(3, 5)
        tick = 5.0
        order_ids = []

        for level in range(num_levels):
            if layer_side == "bid":
                level_price = price - tick * (level + 1)
            else:
                level_price = price + tick * (level + 1)

            order_id = f"LY-O-{ep}-{level}"
            order_ids.append(order_id)
            qty = round(random.uniform(2.0, 10.0), 4)

            t += timedelta(milliseconds=random.uniform(20, 100))
            events.append({
                "timestamp_ms": datetime_to_ms(t),
                "timestamp": t.isoformat(),
                "symbol": symbol,
                "event_type": "place",
                "side": layer_side,
                "price": round(level_price, 2),
                "quantity": qty,
                "order_id": order_id,
            })

        # Synchronized cancellation after 200-1000ms
        cancel_delay = random.uniform(200, 1000)
        t += timedelta(milliseconds=cancel_delay)

        for order_id in order_ids:
            events.append({
                "timestamp_ms": datetime_to_ms(t),
                "timestamp": t.isoformat(),
                "symbol": symbol,
                "event_type": "cancel",
                "side": layer_side,
                "price": 0,
                "quantity": 0,
                "order_id": order_id,
                "lifetime_ms": int(cancel_delay),
            })

        # Opposite-side execution
        exec_side = "sell" if layer_side == "bid" else "buy"
        t += timedelta(milliseconds=random.uniform(10, 100))
        events.append({
            "timestamp_ms": datetime_to_ms(t),
            "timestamp": t.isoformat(),
            "symbol": symbol,
            "event_type": "trade",
            "side": exec_side,
            "price": round(price, 2),
            "quantity": round(random.uniform(2.0, 8.0), 4),
            "trade_id": f"LY-EX-{ep:06d}",
        })

        price += random.gauss(0, 5)

    return events


def generate_quote_stuffing_scenario(
    n_bursts: int = 5,
    symbol: str = "btcusdt",
    base_price: float = 50000.0,
    start_time: datetime = None,
) -> List[Dict[str, Any]]:
    """
    Generate a quote stuffing scenario.

    Pattern: Bursts of rapid order/cancel cycles (100+ per second).
    """
    start = start_time or now_utc()
    events = []
    price = base_price
    t = start

    for burst in range(n_bursts):
        # Normal between bursts
        for _ in range(random.randint(10, 20)):
            t += timedelta(milliseconds=random.uniform(500, 3000))
            events.append({
                "timestamp_ms": datetime_to_ms(t),
                "timestamp": t.isoformat(),
                "symbol": symbol,
                "event_type": "trade",
                "side": random.choice(["buy", "sell"]),
                "price": round(price + random.gauss(0, 5), 2),
                "quantity": round(random.uniform(0.01, 1.0), 6),
                "trade_id": f"QS-T-{len(events):06d}",
            })

        # Quote stuffing burst
        burst_size = random.randint(50, 150)
        for i in range(burst_size):
            order_id = f"QS-O-{burst}-{i}"
            side = random.choice(["bid", "ask"])
            offset = random.uniform(0.01, 0.5)
            if side == "bid":
                order_price = price - offset
            else:
                order_price = price + offset

            # Place
            t += timedelta(milliseconds=random.uniform(5, 15))
            events.append({
                "timestamp_ms": datetime_to_ms(t),
                "timestamp": t.isoformat(),
                "symbol": symbol,
                "event_type": "place",
                "side": side,
                "price": round(order_price, 2),
                "quantity": round(random.uniform(0.01, 0.5), 6),
                "order_id": order_id,
            })

            # Cancel immediately
            cancel_ms = random.uniform(5, 20)
            t += timedelta(milliseconds=cancel_ms)
            events.append({
                "timestamp_ms": datetime_to_ms(t),
                "timestamp": t.isoformat(),
                "symbol": symbol,
                "event_type": "cancel",
                "side": side,
                "price": round(order_price, 2),
                "quantity": 0,
                "order_id": order_id,
                "lifetime_ms": int(cancel_ms),
            })

        price += random.gauss(0, 3)

    return events
