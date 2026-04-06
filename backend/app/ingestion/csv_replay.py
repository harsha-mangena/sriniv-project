"""CSV/historical data replay ingestion source."""

import asyncio
import csv
from pathlib import Path
from typing import AsyncIterator, Optional
from datetime import datetime, timezone

from app.ingestion.base import IngestionSource, MarketEvent
from app.utils.logger import get_logger
from app.utils.time_utils import ms_to_datetime

logger = get_logger(__name__)


class CSVReplaySource(IngestionSource):
    """
    Replays historical market data from CSV files.

    Supports trade CSVs and order event CSVs with configurable playback speed.
    CSV format expected:
    - Trades: timestamp_ms, symbol, side, price, quantity, trade_id
    - Orders: timestamp_ms, symbol, event_type, side, price, quantity, order_id
    """

    def __init__(
        self,
        file_path: str,
        speed_multiplier: float = 1.0,
        data_type: str = "auto",
        loop: bool = False,
    ):
        self._file_path = Path(file_path)
        self._speed_multiplier = speed_multiplier
        self._data_type = data_type  # 'trade', 'order', or 'auto'
        self._loop = loop
        self._connected = False
        self._rows = []

    @property
    def source_name(self) -> str:
        return "csv_replay"

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        """Load CSV file into memory."""
        if not self._file_path.exists():
            raise FileNotFoundError(f"CSV file not found: {self._file_path}")

        self._rows = []
        with open(self._file_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                self._rows.append(row)

        self._connected = True
        logger.info(
            "csv_replay_loaded",
            file=str(self._file_path),
            rows=len(self._rows),
        )

    async def disconnect(self) -> None:
        self._connected = False
        self._rows = []

    async def stream(self) -> AsyncIterator[MarketEvent]:
        """Yield events from CSV with timing simulation."""
        while self._connected:
            prev_ts: Optional[float] = None

            for row in self._rows:
                if not self._connected:
                    return

                ts_ms = float(row.get("timestamp_ms", row.get("timestamp", 0)))

                # Simulate inter-event timing
                if prev_ts is not None and self._speed_multiplier > 0:
                    delay = (ts_ms - prev_ts) / 1000.0 / self._speed_multiplier
                    if delay > 0:
                        await asyncio.sleep(min(delay, 1.0))
                prev_ts = ts_ms

                event = self._parse_row(row, ts_ms)
                if event:
                    yield event

            if not self._loop:
                break

        self._connected = False

    def _detect_type(self, row: dict) -> str:
        """Auto-detect row type from columns."""
        if self._data_type != "auto":
            return self._data_type
        if "event_type" in row:
            return "order"
        if "trade_id" in row or "side" in row:
            return "trade"
        return "trade"

    def _parse_row(self, row: dict, ts_ms: float) -> Optional[MarketEvent]:
        """Parse a CSV row into a MarketEvent."""
        row_type = self._detect_type(row)
        timestamp = ms_to_datetime(int(ts_ms))
        symbol = row.get("symbol", "btcusdt").lower()

        if row_type == "trade":
            price = float(row.get("price", 0))
            quantity = float(row.get("quantity", 0))
            side = row.get("side", "buy").lower()
            return MarketEvent(
                event_type="trade",
                symbol=symbol,
                timestamp=timestamp,
                data={
                    "trade_id": row.get("trade_id", ""),
                    "price": price,
                    "quantity": quantity,
                    "side": side,
                },
                source="csv_replay",
                price=price,
                quantity=quantity,
                side=side,
            )
        elif row_type == "order":
            evt = row.get("event_type", "place")
            price = float(row.get("price", 0))
            quantity = float(row.get("quantity", 0))
            side = row.get("side", "bid").lower()
            return MarketEvent(
                event_type=f"order_{evt}",
                symbol=symbol,
                timestamp=timestamp,
                data={
                    "order_id": row.get("order_id", ""),
                    "event_type": evt,
                    "price": price,
                    "quantity": quantity,
                    "side": side,
                    "lifetime_ms": int(row.get("lifetime_ms", 0)) if row.get("lifetime_ms") else None,
                },
                source="csv_replay",
                order_id=row.get("order_id"),
                price=price,
                quantity=quantity,
                side=side,
            )
        return None
