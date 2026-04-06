"""REST API endpoints for the surveillance platform."""

from typing import Optional
from fastapi import APIRouter, Query, HTTPException

from app.api.schemas import (
    AlertResponse,
    AlertListResponse,
    OrderBookResponse,
    TradeListResponse,
    TradeResponse,
    FeatureResponse,
    DashboardStats,
    HealthResponse,
    ReplayStartRequest,
    ReplayInjectRequest,
    ReplayStatusResponse,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api")


def _get_app_state():
    """Get application state - imported lazily to avoid circular imports."""
    from app.main import app_state
    return app_state


# --- Health ---

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    state = _get_app_state()
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        database="connected" if state.get("db_connected") else "disconnected",
        redis="connected" if state.get("redis_connected") else "disconnected",
        ingestion="running" if state.get("ingestion_running") else "stopped",
    )


# --- Alerts ---

@router.get("/alerts", response_model=AlertListResponse)
async def list_alerts(
    symbol: Optional[str] = Query(None),
    alert_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    min_confidence: Optional[float] = Query(None),
    resolved: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """List alerts with optional filters."""
    state = _get_app_state()
    alerts = state.get("alerts", [])

    # Apply filters
    filtered = alerts
    if symbol:
        filtered = [a for a in filtered if a.get("symbol") == symbol.lower()]
    if alert_type:
        filtered = [a for a in filtered if a.get("alert_type") == alert_type]
    if severity:
        filtered = [a for a in filtered if a.get("severity") == severity]
    if min_confidence is not None:
        filtered = [a for a in filtered if a.get("confidence_score", 0) >= min_confidence]
    if resolved is not None:
        filtered = [a for a in filtered if a.get("resolved", False) == resolved]

    # Sort by timestamp descending
    filtered.sort(key=lambda a: a.get("timestamp", ""), reverse=True)

    # Paginate
    total = len(filtered)
    start = (page - 1) * page_size
    end = start + page_size
    page_alerts = filtered[start:end]

    return AlertListResponse(
        alerts=[AlertResponse(**a) for a in page_alerts],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/alerts/{alert_id}", response_model=AlertResponse)
async def get_alert(alert_id: int):
    """Get a specific alert by ID."""
    state = _get_app_state()
    alerts = state.get("alerts", [])

    for alert in alerts:
        if alert.get("id") == alert_id:
            return AlertResponse(**alert)

    raise HTTPException(status_code=404, detail="Alert not found")


# --- Order Book ---

@router.get("/orderbook/{symbol}", response_model=OrderBookResponse)
async def get_orderbook(symbol: str):
    """Get current order book state for a symbol."""
    state = _get_app_state()
    feature_engine = state.get("feature_engine")

    if not feature_engine:
        raise HTTPException(status_code=503, detail="Feature engine not initialized")

    book = feature_engine.get_order_book(symbol.lower())
    if not book:
        return OrderBookResponse(
            symbol=symbol.lower(),
            bids=[],
            asks=[],
        )

    snapshot = book.get_snapshot()
    return OrderBookResponse(**snapshot)


# --- Trades ---

@router.get("/trades/{symbol}", response_model=TradeListResponse)
async def get_trades(
    symbol: str,
    limit: int = Query(50, ge=1, le=500),
):
    """Get recent trades for a symbol."""
    state = _get_app_state()
    feature_engine = state.get("feature_engine")

    if not feature_engine:
        raise HTTPException(status_code=503, detail="Feature engine not initialized")

    trades = feature_engine.get_recent_trades(symbol.lower(), limit)
    return TradeListResponse(
        trades=[TradeResponse(**t) for t in trades],
        symbol=symbol.lower(),
        count=len(trades),
    )


# --- Features ---

@router.get("/features/{symbol}", response_model=FeatureResponse)
async def get_features(symbol: str):
    """Get current computed features for a symbol."""
    state = _get_app_state()
    feature_engine = state.get("feature_engine")

    if not feature_engine:
        raise HTTPException(status_code=503, detail="Feature engine not initialized")

    features = feature_engine.compute_features(symbol.lower())
    return FeatureResponse(**features)


# --- Stats ---

@router.get("/stats", response_model=DashboardStats)
async def get_stats():
    """Get dashboard statistics."""
    state = _get_app_state()
    alerts = state.get("alerts", [])

    from app.replay.simulator import simulator
    from app.ingestion.event_bus import event_bus

    alerts_by_type = {}
    critical = high = medium = low = 0

    for alert in alerts:
        atype = alert.get("alert_type", "unknown")
        alerts_by_type[atype] = alerts_by_type.get(atype, 0) + 1
        sev = alert.get("severity", "low")
        if sev == "critical":
            critical += 1
        elif sev == "high":
            high += 1
        elif sev == "medium":
            medium += 1
        else:
            low += 1

    import time
    uptime = time.time() - state.get("start_time", time.time())

    return DashboardStats(
        total_alerts=len(alerts),
        critical_alerts=critical,
        high_alerts=high,
        medium_alerts=medium,
        low_alerts=low,
        active_symbols=state.get("active_symbols", []),
        events_processed=event_bus.event_count,
        alerts_by_type=alerts_by_type,
        replay_status=ReplayStatusResponse(**simulator.status),
        uptime_seconds=round(uptime, 1),
    )


# --- Replay ---

@router.post("/replay/start")
async def start_replay(request: ReplayStartRequest):
    """Start a replay scenario."""
    from app.replay.simulator import simulator

    result = await simulator.start_scenario(
        scenario=request.scenario,
        symbol=request.symbol,
        speed=request.speed,
        n_events=request.n_events,
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.post("/replay/stop")
async def stop_replay():
    """Stop current replay."""
    from app.replay.simulator import simulator
    return await simulator.stop()


@router.post("/replay/inject")
async def inject_event(request: ReplayInjectRequest):
    """Inject a synthetic manipulation event."""
    from app.replay.simulator import simulator

    result = await simulator.inject_event(
        event_type=request.event_type,
        symbol=request.symbol,
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result
