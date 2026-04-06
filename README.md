# Market Manipulation Surveillance Platform

**AI-powered real-time surveillance system for detecting market manipulation in crypto order-driven markets.**

Combines rule-based surveillance, machine learning anomaly detection, and custom microstructure algorithms with explainable scoring to detect spoofing, wash trading, layering, and quote stuffing patterns.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        DATA SOURCES                             │
│  Binance WebSocket │ CSV Replay │ Synthetic Generator           │
└──────────┬────────────────┬────────────────┬────────────────────┘
           │                │                │
           ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      EVENT BUS (Async Queue)                    │
└──────────────────────────────┬──────────────────────────────────┘
                               │
           ┌───────────────────┼───────────────────┐
           ▼                   ▼                   ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────────┐
│  ORDER BOOK      │ │ FEATURE ENGINE   │ │  STORAGE             │
│  State Manager   │ │ cancel_rate      │ │  PostgreSQL + Redis  │
│  Bid/Ask Levels  │ │ order_to_trade   │ └──────────────────────┘
│  Order Tracking  │ │ imbalance        │
└──────────────────┘ │ burstiness       │
                     │ z-scores         │
                     │ entropy          │
                     └────────┬─────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐  ┌──────────────────┐  ┌──────────────────────┐
│ RULE-BASED    │  │ ML DETECTORS     │  │ CUSTOM MICROSTRUCTURE│
│ • Spoofing    │  │ • Isolation      │  │ • Liquidity Mirage   │
│ • Wash Trade  │  │   Forest         │  │ • Layering Pressure  │
│ • Layering    │  │ • LSTM           │  │ • Trade Loop Symmetry│
│               │  │   Autoencoder    │  │ • Book Shock Div.    │
│               │  │ • SHAP           │  │ • Intent-Outcome     │
└───────┬───────┘  └────────┬─────────┘  └──────────┬───────────┘
        │                   │                        │
        └───────────────────┼────────────────────────┘
                            ▼
               ┌──────────────────────┐
               │    SCORING ENGINE    │
               │  Weighted Fusion     │
               │  Severity Bucketing  │
               │  NL Explanations     │
               └──────────┬───────────┘
                          │
              ┌───────────┼───────────┐
              ▼                       ▼
     ┌──────────────┐      ┌──────────────────┐
     │  REST API     │      │  WebSocket       │
     │  /api/alerts  │      │  /ws/alerts      │
     │  /api/trades  │      │  /ws/orderbook   │
     │  /api/replay  │      │  /ws/trades      │
     └──────────────┘      └──────────────────┘
```

## Key Features

### Detection Algorithms

| Detector | Type | Description |
|----------|------|-------------|
| **Spoofing Rules** | Rule-Based | Cancel rate, order lifetime, large order cancellation patterns |
| **Wash Trading Rules** | Rule-Based | Trade loop detection, symmetric timing/size, volume recycling |
| **Layering Rules** | Rule-Based | Multi-level stacking, synchronized cancellation |
| **Isolation Forest** | ML | Unsupervised anomaly detection on feature vectors |
| **LSTM Autoencoder** | ML | Sequence anomaly detection via reconstruction error |
| **Liquidity Mirage Score** | Microstructure | Detects deceptive displayed depth (phantom liquidity) |
| **Layering Pressure Index** | Microstructure | Order cluster density × impersistence × sync cancel rate |
| **Trade Loop Symmetry** | Microstructure | Timing/size symmetry × volume recycling × loop frequency |
| **Book Shock Divergence** | Microstructure | Order book pressure vs actual execution direction mismatch |
| **Intent-Outcome Mismatch** | Microstructure | Cosine similarity between intent and outcome vectors |

### Scoring Engine

All detector outputs are fused into a unified confidence score:

```
final_score = w_rule × max(rule_scores) + w_ml × ml_anomaly + w_custom × avg(custom_scores)
```

Severity bucketing: **Critical** (>85) → **High** (>65) → **Medium** (>40) → **Low**

Every alert includes natural language explanations identifying which detectors fired, the specific features that were abnormal, and why the pattern is suspicious.

### Data Sources

- **Binance WebSocket**: Real-time order book depth + trade streams (public, no API key)
- **CSV Replay**: Load historical data from CSV files with configurable playback speed
- **Synthetic Generator**: Generates realistic market data with injectable manipulation patterns
- **Replay Simulator**: Pre-built scenarios for spoofing, wash trading, layering, quote stuffing

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.11+, FastAPI, uvicorn |
| ML | scikit-learn, PyTorch, SHAP |
| Database | PostgreSQL 16, SQLAlchemy (async) |
| Cache | Redis 7 |
| Real-time | WebSockets, async event bus |
| Data | Binance public WebSocket API |
| Testing | pytest, pytest-asyncio |
| Deployment | Docker, docker-compose |

## Quick Start

### Option 1: Docker (Recommended)

```bash
# Clone and start all services
git clone https://github.com/harsha-mangena/sriniv-project.git
cd sriniv-project
git checkout feature/market-surveillance-platform

# Start with Docker
make docker-build
make docker-up

# API available at http://localhost:8000
# Docs at http://localhost:8000/docs
```

### Option 2: Local Development

```bash
# Setup
chmod +x setup.sh
./setup.sh
source venv/bin/activate

# Start PostgreSQL and Redis (or use Docker for just these)
docker-compose up -d postgres redis

# Run the server
make run

# Run tests
make test
```

## API Endpoints

### REST API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Health check with service status |
| `GET` | `/api/alerts` | List alerts with filters (symbol, type, severity, confidence) |
| `GET` | `/api/alerts/{id}` | Alert detail with full explanation |
| `GET` | `/api/orderbook/{symbol}` | Current order book state |
| `GET` | `/api/trades/{symbol}` | Recent trades stream |
| `GET` | `/api/features/{symbol}` | Current computed features |
| `GET` | `/api/stats` | Dashboard statistics |
| `POST` | `/api/replay/start` | Start a replay scenario |
| `POST` | `/api/replay/stop` | Stop current replay |
| `POST` | `/api/replay/inject` | Inject a synthetic manipulation event |

### WebSocket Streams

| Endpoint | Description |
|----------|-------------|
| `ws://localhost:8000/ws/alerts` | Real-time alert notifications |
| `ws://localhost:8000/ws/orderbook/{symbol}` | Live order book updates |
| `ws://localhost:8000/ws/trades/{symbol}` | Live trade stream |

### Example API Usage

```bash
# Get alerts filtered by type and severity
curl http://localhost:8000/api/alerts?alert_type=spoofing&severity=high

# Get current features for BTC
curl http://localhost:8000/api/features/btcusdt

# Start a spoofing replay scenario
curl -X POST http://localhost:8000/api/replay/start \
  -H "Content-Type: application/json" \
  -d '{"scenario": "spoofing", "symbol": "btcusdt", "speed": 2.0, "n_events": 100}'

# Inject a wash trading event
curl -X POST http://localhost:8000/api/replay/inject \
  -H "Content-Type: application/json" \
  -d '{"event_type": "wash_trading", "symbol": "btcusdt"}'
```

## Project Structure

```
backend/
├── app/
│   ├── main.py                          # FastAPI app with lifespan
│   ├── config.py                        # Pydantic settings
│   ├── api/
│   │   ├── routes.py                    # REST endpoints
│   │   ├── websocket.py                 # WebSocket handlers
│   │   └── schemas.py                   # Pydantic models
│   ├── ingestion/
│   │   ├── base.py                      # Abstract ingestion interface
│   │   ├── binance_ws.py                # Binance WebSocket connector
│   │   ├── csv_replay.py                # CSV replay source
│   │   ├── synthetic.py                 # Synthetic data generator
│   │   └── event_bus.py                 # Async pub/sub event bus
│   ├── features/
│   │   ├── order_book.py                # Order book state management
│   │   ├── feature_engine.py            # Feature extraction pipeline
│   │   └── rolling_stats.py             # Rolling statistics
│   ├── detectors/
│   │   ├── base.py                      # Abstract detector interface
│   │   ├── rules/                       # Rule-based detectors
│   │   ├── ml/                          # ML detectors
│   │   └── custom/                      # 5 microstructure detectors
│   ├── scoring/
│   │   └── engine.py                    # Unified scoring engine
│   ├── storage/
│   │   ├── database.py                  # SQLAlchemy async engine
│   │   ├── models.py                    # ORM models
│   │   └── cache.py                     # Redis cache wrapper
│   ├── replay/
│   │   ├── simulator.py                 # Replay controller
│   │   └── scenarios.py                 # Pre-built scenarios
│   └── utils/
│       ├── logger.py                    # Structured logging
│       └── time_utils.py                # Timestamp utilities
├── tests/                               # Comprehensive test suite
├── data/sample/                         # Sample CSV datasets
├── models/                              # Saved ML models
├── requirements.txt
├── Dockerfile
└── alembic/                             # DB migrations
```

## Custom Detector Formulas

### Liquidity Mirage Score (LMS)
```
LMS = w1·(displayed_depth/avg_depth) + w2·(cancel_velocity/baseline)
    + w3·(1-execution_ratio) + w4·(1/avg_lifetime) + w5·refill_frequency
```

### Layering Pressure Index (LPI)
```
LPI = cluster_density × (1/persistence) × sync_cancel_score × opposite_execution_volume
```

### Trade Loop Symmetry Score (TLSS)
```
TLSS = (1-timing_CV) × (1-size_CV) × volume_recycling × loop_frequency
```

### Book Shock vs Execution Divergence (BSED)
```
BSED = |normalized_pressure_signal - normalized_execution_direction|
```

### Intent-Outcome Mismatch (IOME)
```
IOME = 1 - cosine_similarity(intent_vector, outcome_vector)
```

## Testing

```bash
make test              # Run all tests
make test-features     # Feature engineering tests
make test-rules        # Rule detector tests
make test-ml           # ML detector tests
make test-custom       # Custom detector tests
make test-scoring      # Scoring engine tests
make test-integration  # Full pipeline tests
make test-synthetic    # Synthetic data tests
make test-cov          # Tests with coverage report
```

## Training ML Models

```bash
# Train both Isolation Forest and LSTM Autoencoder on synthetic data
make train
```

The trainer generates normal market data, extracts features, and trains both models. Trained models are saved to `backend/models/` and loaded automatically on startup.

---

## Resume-Worthy Project Summary

**Market Manipulation Surveillance Platform** — Designed and built a production-grade real-time surveillance system for detecting market manipulation in cryptocurrency markets, processing live order book and trade data through a multi-layered detection pipeline.

**Key achievements:**
- Engineered a **10-detector ensemble** combining rule-based heuristics, unsupervised ML (Isolation Forest, LSTM Autoencoder), and 5 custom microstructure algorithms with SHAP-based explainability
- Implemented real-time **order book state management** with streaming feature extraction (cancel rate, bid-ask imbalance, depth concentration, burstiness, rolling z-scores, Shannon entropy)
- Built a **unified scoring engine** that fuses heterogeneous detector outputs into calibrated confidence scores with natural language explanations
- Developed a **synthetic data generator** with injectable manipulation patterns (spoofing, wash trading, layering, quote stuffing) for backtesting and model training
- Created a **high-throughput async pipeline** (FastAPI + WebSockets + async event bus) processing real-time Binance market data with sub-second alert latency
- Applied research concepts from **market microstructure theory**: Hawkes process-inspired burstiness measures, network-based wash trade detection, cosine similarity-based intent-outcome mismatch analysis

**Technologies:** Python, FastAPI, PyTorch, scikit-learn, SHAP, SQLAlchemy, PostgreSQL, Redis, WebSockets, Docker
