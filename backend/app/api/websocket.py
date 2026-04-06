"""WebSocket handlers for real-time data streaming."""

import asyncio
import json
from typing import Set
from fastapi import WebSocket, WebSocketDisconnect
from app.ingestion.event_bus import event_bus
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for live data streaming."""

    def __init__(self):
        self._alert_connections: Set[WebSocket] = set()
        self._orderbook_connections: dict[str, Set[WebSocket]] = {}
        self._trade_connections: dict[str, Set[WebSocket]] = {}

    async def connect_alerts(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._alert_connections.add(websocket)
        logger.info("ws_alert_connected", total=len(self._alert_connections))

    async def disconnect_alerts(self, websocket: WebSocket) -> None:
        self._alert_connections.discard(websocket)

    async def connect_orderbook(self, websocket: WebSocket, symbol: str) -> None:
        await websocket.accept()
        if symbol not in self._orderbook_connections:
            self._orderbook_connections[symbol] = set()
        self._orderbook_connections[symbol].add(websocket)

    async def disconnect_orderbook(self, websocket: WebSocket, symbol: str) -> None:
        if symbol in self._orderbook_connections:
            self._orderbook_connections[symbol].discard(websocket)

    async def connect_trades(self, websocket: WebSocket, symbol: str) -> None:
        await websocket.accept()
        if symbol not in self._trade_connections:
            self._trade_connections[symbol] = set()
        self._trade_connections[symbol].add(websocket)

    async def disconnect_trades(self, websocket: WebSocket, symbol: str) -> None:
        if symbol in self._trade_connections:
            self._trade_connections[symbol].discard(websocket)

    async def broadcast_alert(self, alert_data: dict) -> None:
        """Send alert to all connected alert WebSocket clients."""
        dead = set()
        message = json.dumps(alert_data, default=str)
        for ws in self._alert_connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)
        self._alert_connections -= dead

    async def broadcast_orderbook(self, symbol: str, data: dict) -> None:
        """Send order book update to subscribers of a symbol."""
        connections = self._orderbook_connections.get(symbol, set())
        dead = set()
        message = json.dumps(data, default=str)
        for ws in connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)
        if dead:
            self._orderbook_connections[symbol] -= dead

    async def broadcast_trade(self, symbol: str, data: dict) -> None:
        """Send trade update to subscribers of a symbol."""
        connections = self._trade_connections.get(symbol, set())
        dead = set()
        message = json.dumps(data, default=str)
        for ws in connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)
        if dead:
            self._trade_connections[symbol] -= dead

    @property
    def alert_count(self) -> int:
        return len(self._alert_connections)

    @property
    def total_connections(self) -> int:
        total = len(self._alert_connections)
        for conns in self._orderbook_connections.values():
            total += len(conns)
        for conns in self._trade_connections.values():
            total += len(conns)
        return total


# Global manager instance
ws_manager = ConnectionManager()


async def websocket_alert_handler(websocket: WebSocket):
    """Handle WebSocket connections for live alert streaming."""
    await ws_manager.connect_alerts(websocket)
    try:
        while True:
            # Keep connection alive; optionally receive client messages
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                # Client can send filter preferences
                logger.debug("ws_alert_message", data=data)
            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect_alerts(websocket)


async def websocket_orderbook_handler(websocket: WebSocket, symbol: str):
    """Handle WebSocket connections for live order book updates."""
    symbol = symbol.lower()
    await ws_manager.connect_orderbook(websocket, symbol)
    try:
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect_orderbook(websocket, symbol)


async def websocket_trade_handler(websocket: WebSocket, symbol: str):
    """Handle WebSocket connections for live trade streaming."""
    symbol = symbol.lower()
    await ws_manager.connect_trades(websocket, symbol)
    try:
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect_trades(websocket, symbol)
