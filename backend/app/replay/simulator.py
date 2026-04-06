"""Replay simulator for historical data with synthetic injection."""

import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

from app.ingestion.base import MarketEvent
from app.ingestion.event_bus import event_bus
from app.replay.scenarios import (
    generate_normal_trades,
    generate_spoofing_scenario,
    generate_wash_trading_scenario,
    generate_layering_scenario,
    generate_quote_stuffing_scenario,
)
from app.utils.logger import get_logger
from app.utils.time_utils import ms_to_datetime, now_utc

logger = get_logger(__name__)

SCENARIO_GENERATORS = {
    "normal": generate_normal_trades,
    "spoofing": generate_spoofing_scenario,
    "wash_trading": generate_wash_trading_scenario,
    "layering": generate_layering_scenario,
    "quote_stuffing": generate_quote_stuffing_scenario,
}


class ReplaySimulator:
    """
    Replays historical data and injects synthetic incidents.

    Supports:
    - Replaying CSV data through the event bus
    - Running pre-built manipulation scenarios
    - Injecting synthetic events into a live stream
    """

    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._current_scenario: Optional[str] = None
        self._events_processed = 0

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def status(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "scenario": self._current_scenario,
            "events_processed": self._events_processed,
        }

    async def start_scenario(
        self,
        scenario: str,
        symbol: str = "btcusdt",
        speed: float = 1.0,
        n_events: int = 50,
    ) -> Dict[str, Any]:
        """
        Start replaying a manipulation scenario.

        Args:
            scenario: One of 'normal', 'spoofing', 'wash_trading', 'layering', 'quote_stuffing'
            symbol: Trading symbol
            speed: Playback speed multiplier
            n_events: Number of events/episodes to generate
        """
        if self._running:
            return {"error": "Simulator already running", "status": self.status}

        generator = SCENARIO_GENERATORS.get(scenario)
        if not generator:
            return {
                "error": f"Unknown scenario: {scenario}",
                "available": list(SCENARIO_GENERATORS.keys()),
            }

        self._running = True
        self._current_scenario = scenario
        self._events_processed = 0

        # Generate events
        if scenario == "normal":
            events = generator(n_trades=n_events, symbol=symbol)
        else:
            kwargs = {"symbol": symbol}
            if scenario == "spoofing":
                kwargs["n_events"] = n_events
            elif scenario == "wash_trading":
                kwargs["n_loops"] = n_events
            elif scenario == "layering":
                kwargs["n_episodes"] = n_events
            elif scenario == "quote_stuffing":
                kwargs["n_bursts"] = max(1, n_events // 10)
            events = generator(**kwargs)

        logger.info(
            "replay_started",
            scenario=scenario,
            n_events=len(events),
            speed=speed,
        )

        # Start async replay
        self._task = asyncio.create_task(
            self._replay_events(events, speed)
        )

        return {
            "status": "started",
            "scenario": scenario,
            "total_events": len(events),
        }

    async def stop(self) -> Dict[str, Any]:
        """Stop current replay."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        result = {
            "status": "stopped",
            "scenario": self._current_scenario,
            "events_processed": self._events_processed,
        }
        self._current_scenario = None
        return result

    async def inject_event(
        self,
        event_type: str,
        symbol: str = "btcusdt",
        **kwargs,
    ) -> Dict[str, Any]:
        """Inject a single synthetic event into the event bus."""
        now = now_utc()

        if event_type in SCENARIO_GENERATORS:
            # Generate a small burst of the scenario
            generator = SCENARIO_GENERATORS[event_type]
            if event_type == "normal":
                events = generator(n_trades=10, symbol=symbol)
            elif event_type == "spoofing":
                events = generator(n_events=1, symbol=symbol)
            elif event_type == "wash_trading":
                events = generator(n_loops=3, symbol=symbol)
            elif event_type == "layering":
                events = generator(n_episodes=1, symbol=symbol)
            elif event_type == "quote_stuffing":
                events = generator(n_bursts=1, symbol=symbol)
            else:
                events = []

            for event_data in events:
                market_event = self._dict_to_market_event(event_data, symbol)
                await event_bus.publish(market_event)

            return {
                "status": "injected",
                "event_type": event_type,
                "n_events": len(events),
            }

        return {"error": f"Unknown event type: {event_type}"}

    async def _replay_events(self, events: List[Dict], speed: float) -> None:
        """Replay a list of events through the event bus."""
        prev_ts = None

        for event_data in events:
            if not self._running:
                break

            ts_ms = event_data.get("timestamp_ms", 0)

            # Simulate timing
            if prev_ts is not None and speed > 0:
                delay = (ts_ms - prev_ts) / 1000.0 / speed
                if delay > 0:
                    await asyncio.sleep(min(delay, 2.0))

            prev_ts = ts_ms

            symbol = event_data.get("symbol", "btcusdt")
            market_event = self._dict_to_market_event(event_data, symbol)
            await event_bus.publish(market_event)
            self._events_processed += 1

        self._running = False
        logger.info("replay_completed", events_processed=self._events_processed)

    @staticmethod
    def _dict_to_market_event(data: Dict, symbol: str) -> MarketEvent:
        """Convert event dict to MarketEvent."""
        ts_ms = data.get("timestamp_ms", 0)
        timestamp = ms_to_datetime(int(ts_ms)) if ts_ms else now_utc()

        evt_type_raw = data.get("event_type", "trade")
        if evt_type_raw in ("place", "cancel", "modify"):
            event_type = f"order_{evt_type_raw}"
        else:
            event_type = evt_type_raw

        return MarketEvent(
            event_type=event_type,
            symbol=symbol,
            timestamp=timestamp,
            data=data,
            source="replay",
            order_id=data.get("order_id"),
            price=data.get("price"),
            quantity=data.get("quantity"),
            side=data.get("side"),
        )


# Global simulator instance
simulator = ReplaySimulator()
