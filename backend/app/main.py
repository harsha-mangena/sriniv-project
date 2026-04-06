"""FastAPI application entry point for Market Manipulation Surveillance Platform."""

import asyncio
import time
from contextlib import asynccontextmanager
from typing import Dict, Any, List

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.utils.logger import setup_logging, get_logger
from app.api.routes import router
from app.api.websocket import (
    websocket_alert_handler,
    websocket_orderbook_handler,
    websocket_trade_handler,
    ws_manager,
)
from app.ingestion.event_bus import event_bus
from app.ingestion.synthetic import SyntheticDataGenerator
from app.features.feature_engine import FeatureEngine
from app.scoring.engine import ScoringEngine
from app.storage.cache import cache

# Global application state
app_state: Dict[str, Any] = {
    "alerts": [],
    "active_symbols": [],
    "feature_engine": None,
    "scoring_engine": None,
    "db_connected": False,
    "redis_connected": False,
    "ingestion_running": False,
    "start_time": time.time(),
}

logger = get_logger(__name__)


async def _event_processing_loop(
    feature_engine: FeatureEngine,
    scoring_engine: ScoringEngine,
):
    """Main event processing loop: ingest -> features -> detect -> score -> alert."""
    queue = event_bus.subscribe()
    alert_id_counter = 0

    while True:
        try:
            event = await asyncio.wait_for(queue.get(), timeout=5.0)
        except asyncio.TimeoutError:
            continue
        except asyncio.CancelledError:
            break

        try:
            # Process event through feature engine
            features = feature_engine.process_event(event)
            if features is None:
                continue

            symbol = event.symbol

            # Broadcast trade/orderbook via WebSocket
            if event.event_type == "trade":
                await ws_manager.broadcast_trade(symbol, {
                    "type": "trade",
                    "symbol": symbol,
                    "price": event.price,
                    "quantity": event.quantity,
                    "side": event.side,
                    "timestamp": event.timestamp.isoformat(),
                })
            elif event.event_type == "depth_update":
                book = feature_engine.get_order_book(symbol)
                if book:
                    await ws_manager.broadcast_orderbook(symbol, {
                        "type": "orderbook",
                        **book.get_snapshot(),
                    })

            # Run scoring engine
            order_book = feature_engine.get_order_book(symbol)
            recent_trades = feature_engine.get_recent_trades(symbol, limit=50)

            alert = scoring_engine.evaluate(
                features,
                order_book=order_book,
                recent_trades=recent_trades,
            )

            if alert:
                alert_id_counter += 1
                alert["id"] = alert_id_counter

                # Store alert
                app_state["alerts"].append(alert)
                # Keep last 10000 alerts in memory
                if len(app_state["alerts"]) > 10000:
                    app_state["alerts"] = app_state["alerts"][-10000:]

                # Broadcast via WebSocket
                await ws_manager.broadcast_alert(alert)

                logger.info(
                    "alert_generated",
                    id=alert["id"],
                    type=alert["alert_type"],
                    severity=alert["severity"],
                    score=alert["confidence_score"],
                    symbol=alert["symbol"],
                )

        except Exception as e:
            logger.error("processing_error", error=str(e))


async def _start_synthetic_source():
    """Start synthetic data generator for demo mode."""
    for symbol in settings.symbols_list:
        generator = SyntheticDataGenerator(
            symbol=symbol,
            base_price=50000.0 if "btc" in symbol else 3000.0,
            events_per_second=5.0,
            manipulation_probability=0.08,
        )
        await generator.connect()

        async def stream_to_bus(gen=generator):
            try:
                async for event in gen.stream():
                    await event_bus.publish(event)
            except asyncio.CancelledError:
                await gen.disconnect()

        asyncio.create_task(stream_to_bus())

    app_state["ingestion_running"] = True
    logger.info("synthetic_source_started", symbols=settings.symbols_list)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    setup_logging()
    logger.info("app_starting", debug=settings.debug)

    # Initialize feature engine and scoring engine
    feature_engine = FeatureEngine()
    scoring_engine = ScoringEngine()
    app_state["feature_engine"] = feature_engine
    app_state["scoring_engine"] = scoring_engine
    app_state["active_symbols"] = settings.symbols_list

    # Try loading ML models
    for detector in scoring_engine.ml_detectors:
        try:
            if hasattr(detector, 'load'):
                detector.load()
        except Exception:
            pass

    # Connect Redis (optional)
    try:
        await cache.connect()
        app_state["redis_connected"] = cache.available
    except Exception:
        app_state["redis_connected"] = False

    # Start event processing loop
    processing_task = asyncio.create_task(
        _event_processing_loop(feature_engine, scoring_engine)
    )

    # Start synthetic data source (demo mode)
    await _start_synthetic_source()

    logger.info("app_started")
    yield

    # Shutdown
    logger.info("app_shutting_down")
    processing_task.cancel()
    try:
        await processing_task
    except asyncio.CancelledError:
        pass

    await cache.disconnect()
    logger.info("app_stopped")


# Create FastAPI app
app = FastAPI(
    title="Market Manipulation Surveillance Platform",
    description="AI-powered surveillance platform for detecting market manipulation "
                "(spoofing, wash trading, layering, quote stuffing) in crypto markets.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST routes
app.include_router(router)


# WebSocket endpoints
@app.websocket("/ws/alerts")
async def ws_alerts(websocket: WebSocket):
    await websocket_alert_handler(websocket)


@app.websocket("/ws/orderbook/{symbol}")
async def ws_orderbook(websocket: WebSocket, symbol: str):
    await websocket_orderbook_handler(websocket, symbol)


@app.websocket("/ws/trades/{symbol}")
async def ws_trades(websocket: WebSocket, symbol: str):
    await websocket_trade_handler(websocket, symbol)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.debug,
    )
