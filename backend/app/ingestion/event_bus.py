"""Async event queue for distributing market events to consumers."""

import asyncio
from typing import Callable, Awaitable, List, Dict, Any
from app.ingestion.base import MarketEvent
from app.utils.logger import get_logger

logger = get_logger(__name__)


class EventBus:
    """
    Async publish-subscribe event bus for market events.

    Decouples ingestion sources from consumers (feature engine, detectors, storage).
    Supports multiple subscribers per event type with backpressure via bounded queues.
    """

    def __init__(self, max_queue_size: int = 10000):
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}
        self._global_subscribers: List[asyncio.Queue] = []
        self._max_queue_size = max_queue_size
        self._running = False
        self._event_count = 0

    async def publish(self, event: MarketEvent) -> None:
        """Publish an event to all matching subscribers."""
        self._event_count += 1

        # Send to type-specific subscribers
        type_subs = self._subscribers.get(event.event_type, [])
        for queue in type_subs:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # Drop oldest event to prevent blocking
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                queue.put_nowait(event)

        # Send to global subscribers
        for queue in self._global_subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                queue.put_nowait(event)

    def subscribe(self, event_type: str = None) -> asyncio.Queue:
        """
        Subscribe to events. Returns a queue to consume events from.

        If event_type is None, subscribes to ALL events.
        """
        queue = asyncio.Queue(maxsize=self._max_queue_size)
        if event_type is None:
            self._global_subscribers.append(queue)
        else:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue, event_type: str = None) -> None:
        """Remove a subscription."""
        if event_type is None:
            self._global_subscribers = [q for q in self._global_subscribers if q is not queue]
        else:
            if event_type in self._subscribers:
                self._subscribers[event_type] = [
                    q for q in self._subscribers[event_type] if q is not queue
                ]

    @property
    def event_count(self) -> int:
        return self._event_count

    @property
    def subscriber_count(self) -> int:
        total = len(self._global_subscribers)
        for subs in self._subscribers.values():
            total += len(subs)
        return total


# Global event bus instance
event_bus = EventBus()
