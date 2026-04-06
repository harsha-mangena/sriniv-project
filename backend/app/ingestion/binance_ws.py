"""Binance WebSocket connector for real-time market data."""

import asyncio
import json
from typing import AsyncIterator, List, Optional
from datetime import datetime, timezone

import aiohttp

from app.ingestion.base import IngestionSource, MarketEvent
from app.config import settings
from app.utils.logger import get_logger
from app.utils.time_utils import ms_to_datetime

logger = get_logger(__name__)


class BinanceWebSocketSource(IngestionSource):
    """
    Connects to Binance public WebSocket streams for order book depth and trades.

    Uses combined streams: wss://stream.binance.com:9443/ws
    - {symbol}@depth@100ms  - Order book diff updates every 100ms
    - {symbol}@trade        - Individual trade events
    """

    def __init__(self, symbols: Optional[List[str]] = None):
        self._symbols = symbols or settings.symbols_list
        self._session: Optional[aiohttp.ClientSession] = None
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._connected = False
        self._reconnect_delay = 1.0
        self._max_reconnect_delay = 60.0

    @property
    def source_name(self) -> str:
        return "binance"

    @property
    def is_connected(self) -> bool:
        return self._connected

    def _build_stream_url(self) -> str:
        """Build combined WebSocket stream URL for all symbols."""
        streams = []
        for symbol in self._symbols:
            s = symbol.lower()
            streams.append(f"{s}@depth@100ms")
            streams.append(f"{s}@trade")
        stream_path = "/".join(streams)
        return f"{settings.binance_ws_url}/{stream_path}"

    async def connect(self) -> None:
        """Establish WebSocket connection to Binance."""
        self._session = aiohttp.ClientSession()
        url = self._build_stream_url()
        logger.info("binance_connecting", url=url, symbols=self._symbols)
        try:
            self._ws = await self._session.ws_connect(url)
            self._connected = True
            self._reconnect_delay = 1.0
            logger.info("binance_connected", symbols=self._symbols)
        except Exception as e:
            logger.error("binance_connect_failed", error=str(e))
            raise

    async def disconnect(self) -> None:
        """Close WebSocket and HTTP session."""
        self._connected = False
        if self._ws and not self._ws.closed:
            await self._ws.close()
        if self._session and not self._session.closed:
            await self._session.close()
        logger.info("binance_disconnected")

    async def stream(self) -> AsyncIterator[MarketEvent]:
        """Yield parsed market events from Binance WebSocket."""
        while self._connected:
            try:
                async for msg in self._ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        event = self._parse_message(data)
                        if event:
                            yield event
                    elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                        logger.warning("binance_ws_closed", type=str(msg.type))
                        break
            except Exception as e:
                logger.error("binance_stream_error", error=str(e))

            if self._connected:
                # Reconnect with exponential backoff
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(
                    self._reconnect_delay * 2, self._max_reconnect_delay
                )
                try:
                    await self.connect()
                except Exception:
                    continue

    def _parse_message(self, data: dict) -> Optional[MarketEvent]:
        """Parse a Binance WebSocket message into a MarketEvent."""
        event_type = data.get("e")

        if event_type == "depthUpdate":
            return self._parse_depth_update(data)
        elif event_type == "trade":
            return self._parse_trade(data)

        # Combined stream wrapper
        if "stream" in data and "data" in data:
            return self._parse_message(data["data"])

        return None

    def _parse_depth_update(self, data: dict) -> MarketEvent:
        """Parse order book depth update."""
        symbol = data.get("s", "").lower()
        timestamp = ms_to_datetime(data.get("E", 0))

        bids = [[float(p), float(q)] for p, q in data.get("b", [])]
        asks = [[float(p), float(q)] for p, q in data.get("a", [])]

        return MarketEvent(
            event_type="depth_update",
            symbol=symbol,
            timestamp=timestamp,
            data={
                "bids": bids,
                "asks": asks,
                "first_update_id": data.get("U"),
                "final_update_id": data.get("u"),
            },
            source="binance",
        )

    def _parse_trade(self, data: dict) -> MarketEvent:
        """Parse individual trade event."""
        symbol = data.get("s", "").lower()
        timestamp = ms_to_datetime(data.get("T", data.get("E", 0)))
        price = float(data.get("p", 0))
        quantity = float(data.get("q", 0))
        # Binance: m=True means buyer is market maker (sell aggressor)
        is_buyer_maker = data.get("m", False)
        side = "sell" if is_buyer_maker else "buy"

        return MarketEvent(
            event_type="trade",
            symbol=symbol,
            timestamp=timestamp,
            data={
                "trade_id": str(data.get("t", "")),
                "price": price,
                "quantity": quantity,
                "side": side,
                "buyer_order_id": str(data.get("b", "")),
                "seller_order_id": str(data.get("a", "")),
                "is_buyer_maker": is_buyer_maker,
            },
            source="binance",
            price=price,
            quantity=quantity,
            side=side,
        )
