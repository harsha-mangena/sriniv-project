"""Intent-Outcome Mismatch Engine (IOME).

For each time window:
  1. Classify apparent intent from order book activity
  2. Classify realized behavior from actual trades
  3. Compute mismatch_score via cosine similarity:
     intent_vector = normalize(bid_intent_strength, ask_intent_strength)
     outcome_vector = normalize(buy_execution, sell_execution)
     mismatch = 1 - cosine_similarity(intent_vector, outcome_vector)
  4. Track pseudo-entity patterns for repeated mismatches
"""

import math
from typing import Dict, Any, Optional, List, Tuple
from collections import defaultdict

from app.detectors.base import BaseDetector, DetectionResult
from app.features.order_book import OrderBook


class IntentOutcomeMismatchDetector(BaseDetector):
    """
    Intent-Outcome Mismatch Engine.

    Compares visible market intent (order book activity) with actual outcomes
    (trade execution) to identify manipulative discrepancies. Tracks
    pseudo-entities by order size/timing clusters.
    """

    def __init__(
        self,
        threshold: float = 0.5,
        entity_size_tolerance: float = 0.1,
        entity_window_ms: float = 5000.0,
    ):
        self._threshold = threshold
        self._entity_size_tolerance = entity_size_tolerance
        self._entity_window_ms = entity_window_ms
        # Track pseudo-entity mismatch history
        self._entity_mismatches: Dict[str, List[float]] = defaultdict(list)
        self._max_entity_history = 50

    @property
    def name(self) -> str:
        return "intent_outcome_mismatch"

    @property
    def category(self) -> str:
        return "custom"

    @property
    def description(self) -> str:
        return "Intent-Outcome Mismatch Engine detecting divergence between displayed intent and execution"

    def detect(self, features: Dict[str, Any], **kwargs) -> Optional[DetectionResult]:
        """Compute IOME score and flag mismatches."""
        order_book: Optional[OrderBook] = kwargs.get("order_book")
        recent_trades: List[Dict] = kwargs.get("recent_trades", [])

        if not order_book or not recent_trades:
            return None

        # Step 1: Classify apparent intent from order book
        bid_intent, ask_intent = self._classify_intent(features, order_book)

        # Step 2: Classify realized behavior from trades
        buy_execution, sell_execution = self._classify_outcome(recent_trades)

        # Step 3: Compute mismatch via cosine similarity
        intent_vector = (bid_intent, ask_intent)
        outcome_vector = (buy_execution, sell_execution)
        mismatch = self._compute_mismatch(intent_vector, outcome_vector)

        # Step 4: Track pseudo-entity patterns
        entity_score = self._track_entities(order_book, recent_trades, mismatch)

        # Combined IOME score
        iome = mismatch * 0.7 + entity_score * 0.3

        if iome < self._threshold:
            return None

        score = min(1.0, iome)

        # Describe the mismatch
        intent_desc = "buy intent" if bid_intent > ask_intent else "sell intent"
        outcome_desc = "net buying" if buy_execution > sell_execution else "net selling"

        contributing = [
            f"bid_intent={bid_intent:.3f}",
            f"ask_intent={ask_intent:.3f}",
            f"buy_execution={buy_execution:.3f}",
            f"sell_execution={sell_execution:.3f}",
            f"mismatch={mismatch:.3f}",
        ]
        if entity_score > 0.3:
            contributing.append(f"entity_pattern_score={entity_score:.3f}")

        # Determine alert type
        if mismatch > 0.6:
            alert_type = "spoofing"
            explanation = (
                f"Intent-Outcome Mismatch: {iome:.3f}. "
                f"Book shows {intent_desc} but execution shows {outcome_desc}. "
                f"Strong divergence suggests manipulative intent."
            )
        else:
            alert_type = "layering"
            explanation = (
                f"Intent-Outcome Mismatch: {iome:.3f}. "
                f"Moderate divergence between {intent_desc} and {outcome_desc}."
            )

        return DetectionResult(
            event_type=alert_type,
            score=score,
            explanation=explanation,
            raw_features={
                "iome": iome,
                "mismatch": mismatch,
                "entity_score": entity_score,
                "bid_intent": bid_intent,
                "ask_intent": ask_intent,
                "buy_execution": buy_execution,
                "sell_execution": sell_execution,
            },
            detector_name=self.name,
            detector_category=self.category,
            contributing_factors=contributing,
            confidence=min(1.0, score * 1.1),
        )

    def _classify_intent(self, features: Dict[str, Any], order_book: OrderBook) -> Tuple[float, float]:
        """
        Classify apparent intent from order book activity.

        Returns (bid_intent_strength, ask_intent_strength) normalized to [0, 1].
        """
        bid_vol = features.get("bid_volume", 0)
        ask_vol = features.get("ask_volume", 0)
        total = bid_vol + ask_vol

        if total < 1e-10:
            return 0.0, 0.0

        # Normalize volumes
        bid_strength = bid_vol / total
        ask_strength = ask_vol / total

        # Boost by order arrival rate on each side
        recent_orders = order_book.get_recent_orders(50)
        bid_orders = sum(1 for o in recent_orders if o.side == "bid")
        ask_orders = sum(1 for o in recent_orders if o.side == "ask")
        total_orders = bid_orders + ask_orders

        if total_orders > 0:
            bid_rate = bid_orders / total_orders
            ask_rate = ask_orders / total_orders
            bid_strength = (bid_strength + bid_rate) / 2
            ask_strength = (ask_strength + ask_rate) / 2

        return bid_strength, ask_strength

    def _classify_outcome(self, recent_trades: List[Dict]) -> Tuple[float, float]:
        """
        Classify realized behavior from actual trades.

        Returns (buy_execution, sell_execution) normalized to [0, 1].
        """
        buy_vol = sum(
            float(t.get("quantity", 0)) for t in recent_trades if t.get("side") == "buy"
        )
        sell_vol = sum(
            float(t.get("quantity", 0)) for t in recent_trades if t.get("side") == "sell"
        )
        total = buy_vol + sell_vol

        if total < 1e-10:
            return 0.0, 0.0

        return buy_vol / total, sell_vol / total

    def _compute_mismatch(
        self,
        intent: Tuple[float, float],
        outcome: Tuple[float, float],
    ) -> float:
        """
        Compute mismatch as 1 - cosine_similarity between intent and outcome vectors.
        """
        # Cosine similarity
        dot = intent[0] * outcome[0] + intent[1] * outcome[1]
        mag_intent = math.sqrt(intent[0] ** 2 + intent[1] ** 2)
        mag_outcome = math.sqrt(outcome[0] ** 2 + outcome[1] ** 2)

        if mag_intent < 1e-10 or mag_outcome < 1e-10:
            return 0.0

        cosine_sim = dot / (mag_intent * mag_outcome)
        cosine_sim = max(-1.0, min(1.0, cosine_sim))

        mismatch = 1.0 - cosine_sim
        return mismatch

    def _track_entities(
        self,
        order_book: OrderBook,
        recent_trades: List[Dict],
        current_mismatch: float,
    ) -> float:
        """
        Track pseudo-entities by order size/timing clusters.

        Identifies repeated mismatch patterns from similar-sized order groups.
        """
        recent_orders = order_book.get_recent_orders(50)
        if not recent_orders:
            return 0.0

        # Create pseudo-entity keys from order sizes
        for order in recent_orders:
            size_bucket = round(order.quantity * 10) / 10
            entity_key = f"{order.side}_{size_bucket}"

            self._entity_mismatches[entity_key].append(current_mismatch)
            if len(self._entity_mismatches[entity_key]) > self._max_entity_history:
                self._entity_mismatches[entity_key] = self._entity_mismatches[entity_key][-self._max_entity_history:]

        # Find entities with consistently high mismatches
        max_entity_score = 0.0
        for entity_key, mismatches in self._entity_mismatches.items():
            if len(mismatches) >= 3:
                avg_mismatch = sum(mismatches[-10:]) / len(mismatches[-10:])
                consistency = sum(1 for m in mismatches[-10:] if m > self._threshold) / len(mismatches[-10:])
                entity_score = avg_mismatch * consistency
                max_entity_score = max(max_entity_score, entity_score)

        return max_entity_score
