"""Abstract base class for data ingestion sources."""

from abc import ABC, abstractmethod
from typing import AsyncIterator, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class MarketEvent:
    """Unified market event representation."""
    event_type: str  # 'order_place', 'order_cancel', 'order_modify', 'trade', 'depth_update'
    symbol: str
    timestamp: datetime
    data: Dict[str, Any]
    source: str = "unknown"  # 'binance', 'csv', 'synthetic'
    order_id: Optional[str] = None
    side: Optional[str] = None
    price: Optional[float] = None
    quantity: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class IngestionSource(ABC):
    """Abstract interface for market data ingestion."""

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to data source."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to data source."""
        ...

    @abstractmethod
    async def stream(self) -> AsyncIterator[MarketEvent]:
        """Yield market events from the source."""
        ...

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Return name of this ingestion source."""
        ...

    @property
    def is_connected(self) -> bool:
        return False
