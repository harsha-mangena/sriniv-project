"""Integration tests for the ingestion-to-alert pipeline."""

import pytest
import asyncio

from app.ingestion.synthetic import SyntheticDataGenerator
from app.ingestion.event_bus import EventBus
from app.features.feature_engine import FeatureEngine
from app.scoring.engine import ScoringEngine
from app.ingestion.base import MarketEvent


class TestIngestionToAlertPipeline:
    """Test the full pipeline from ingestion to alert generation."""

    @pytest.mark.asyncio
    async def test_full_pipeline_with_normal_data(self):
        """Normal data should produce few or no alerts."""
        engine = FeatureEngine()
        scorer = ScoringEngine()

        gen = SyntheticDataGenerator(
            events_per_second=100,
            manipulation_probability=0.0,
        )
        await gen.connect()

        alerts = []
        count = 0
        async for event in gen.stream():
            features = engine.process_event(event)
            if features:
                order_book = engine.get_order_book(event.symbol)
                recent_trades = engine.get_recent_trades(event.symbol)
                alert = scorer.evaluate(
                    features,
                    order_book=order_book,
                    recent_trades=recent_trades,
                )
                if alert:
                    alerts.append(alert)

            count += 1
            if count >= 100:
                break

        await gen.disconnect()

        # Normal data shouldn't produce many high-severity alerts
        high_alerts = [a for a in alerts if a["severity"] in ("high", "critical")]
        assert len(high_alerts) < len(alerts) * 0.5 or len(alerts) == 0

    @pytest.mark.asyncio
    async def test_full_pipeline_with_manipulation(self):
        """Manipulated data should produce alerts."""
        engine = FeatureEngine()
        scorer = ScoringEngine()

        gen = SyntheticDataGenerator(
            events_per_second=100,
            manipulation_probability=0.5,
        )
        await gen.connect()

        alerts = []
        count = 0
        async for event in gen.stream():
            features = engine.process_event(event)
            if features:
                order_book = engine.get_order_book(event.symbol)
                recent_trades = engine.get_recent_trades(event.symbol)
                alert = scorer.evaluate(
                    features,
                    order_book=order_book,
                    recent_trades=recent_trades,
                )
                if alert:
                    alerts.append(alert)

            count += 1
            if count >= 200:
                break

        await gen.disconnect()

        # Should have generated some alerts
        assert len(alerts) > 0

    @pytest.mark.asyncio
    async def test_event_bus_integration(self):
        """Test event bus pub/sub with feature engine."""
        bus = EventBus()
        engine = FeatureEngine()

        queue = bus.subscribe()

        # Publish events
        gen = SyntheticDataGenerator(events_per_second=100, manipulation_probability=0.0)
        await gen.connect()

        count = 0
        async for event in gen.stream():
            await bus.publish(event)
            count += 1
            if count >= 10:
                break

        await gen.disconnect()

        # Consume from queue
        consumed = 0
        while not queue.empty():
            event = queue.get_nowait()
            engine.process_event(event)
            consumed += 1

        assert consumed == 10
        assert bus.event_count >= 10

    @pytest.mark.asyncio
    async def test_alert_structure_valid(self):
        """Verify alert structure matches expected schema."""
        engine = FeatureEngine()
        scorer = ScoringEngine()

        gen = SyntheticDataGenerator(
            events_per_second=100,
            manipulation_probability=1.0,
            enabled_manipulations=["spoofing"],
        )
        await gen.connect()

        alert = None
        count = 0
        async for event in gen.stream():
            features = engine.process_event(event)
            if features:
                order_book = engine.get_order_book(event.symbol)
                recent_trades = engine.get_recent_trades(event.symbol)
                result = scorer.evaluate(
                    features,
                    order_book=order_book,
                    recent_trades=recent_trades,
                )
                if result:
                    alert = result
                    break

            count += 1
            if count >= 300:
                break

        await gen.disconnect()

        if alert:
            required_keys = [
                "symbol", "alert_type", "severity", "confidence_score",
                "rule_scores", "ml_scores", "custom_scores",
                "explanation", "timestamp",
            ]
            for key in required_keys:
                assert key in alert, f"Missing key: {key}"

            assert alert["severity"] in ("low", "medium", "high", "critical")
            assert 0 <= alert["confidence_score"] <= 100
