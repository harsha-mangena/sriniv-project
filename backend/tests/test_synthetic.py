"""Tests for synthetic data generator."""

import pytest
import asyncio

from app.ingestion.synthetic import SyntheticDataGenerator
from app.ingestion.base import MarketEvent


class TestSyntheticDataGenerator:
    """Tests for SyntheticDataGenerator."""

    def test_properties(self):
        gen = SyntheticDataGenerator()
        assert gen.source_name == "synthetic"
        assert not gen.is_connected

    @pytest.mark.asyncio
    async def test_connect_disconnect(self):
        gen = SyntheticDataGenerator()
        await gen.connect()
        assert gen.is_connected
        await gen.disconnect()
        assert not gen.is_connected

    @pytest.mark.asyncio
    async def test_generates_events(self):
        gen = SyntheticDataGenerator(
            events_per_second=100,
            manipulation_probability=0.0,
        )
        await gen.connect()

        events = []
        count = 0
        async for event in gen.stream():
            events.append(event)
            count += 1
            if count >= 20:
                break

        await gen.disconnect()

        assert len(events) == 20
        for event in events:
            assert isinstance(event, MarketEvent)
            assert event.symbol == "btcusdt"
            assert event.source == "synthetic"

    @pytest.mark.asyncio
    async def test_generates_trades(self):
        gen = SyntheticDataGenerator(
            events_per_second=100,
            manipulation_probability=0.0,
        )
        await gen.connect()

        trades = []
        count = 0
        async for event in gen.stream():
            if event.event_type == "trade":
                trades.append(event)
            count += 1
            if count >= 50:
                break

        await gen.disconnect()
        assert len(trades) > 0

    @pytest.mark.asyncio
    async def test_manipulation_injection(self):
        gen = SyntheticDataGenerator(
            events_per_second=100,
            manipulation_probability=1.0,  # Always inject
            enabled_manipulations=["spoofing"],
        )
        await gen.connect()

        events = []
        count = 0
        async for event in gen.stream():
            events.append(event)
            count += 1
            if count >= 10:
                break

        await gen.disconnect()

        # Should have spoofing-related events
        assert len(events) > 0
        manipulation_events = [e for e in events if e.metadata.get("manipulation") == "spoofing"]
        assert len(manipulation_events) > 0

    @pytest.mark.asyncio
    async def test_custom_symbol(self):
        gen = SyntheticDataGenerator(symbol="ethusdt", base_price=3000.0)
        await gen.connect()

        async for event in gen.stream():
            assert event.symbol == "ethusdt"
            break

        await gen.disconnect()
