# AgriQuant AI

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Models](https://img.shields.io/badge/ML%20Models-8-brightgreen)](https://github.com/agriquant-ai/AgriQuant-AI)
[![Accuracy](https://img.shields.io/badge/Win%20Rate-70%25-success)](https://github.com/agriquant-ai/AgriQuant-AI)
[![Markets](https://img.shields.io/badge/Markets-6-blue)](https://github.com/agriquant-ai/AgriQuant-AI)

**AI-driven weather intelligence for agricultural commodity futures.**

AgriQuant AI analyzes satellite weather data and 40 years of price patterns to predict agricultural commodity moves 48–72 hours before traditional analysts react. Built on Claude Sonnet, NOAA real-time feeds, and a multi-spectral satellite pipeline covering six global markets.

---

## Overview

AgriQuant AI monitors weather events across six agricultural commodity markets and generates probabilistic price impact signals before official USDA and agency reports are published.

The system processes NOAA weather forecasts, satellite imagery, and market data continuously, cross-referencing against a 40-year historical database of weather-driven commodity price moves.

**Backtest Performance (2023–2025):**
- +223% total return (2.5x leveraged futures strategy)
- 70% win rate across 23 trades
- 2.6:1 win/loss ratio
- 1.8 Sharpe ratio
- -21% max drawdown

---

## Markets Covered

| Commodity | Ticker | Exchange | Region | Primary Risk |
|-----------|--------|----------|--------|--------------|
| Orange Juice | FCOJ-A | ICE | Florida, USA | Freeze, hurricane, disease |
| Coffee (Arabica) | KC | ICE | Minas Gerais, Brazil | Frost, drought |
| Cocoa | CC | ICE | Ghana / Ivory Coast | Drought, Harmattan winds |
| Sugar #11 | SB | ICE | Brazil / India | Monsoon, drought |
| Corn | ZC | CME | US Midwest | Drought, derecho, frost |
| Wheat | ZW | CME | Great Plains | Drought, Black Sea risk |

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       AgriQuant AI                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐     ┌──────────────┐     ┌────────────┐ │
│  │   Weather    │────▶│    Claude    │────▶│ Database   │ │
│  │  Collector   │     │   Sonnet 4   │     │ PostgreSQL │ │
│  └──────────────┘     └──────────────┘     └────────────┘ │
│        │                     │                     │        │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                 Main Orchestrator                    │  │
│  │  • 15-min monitoring cycle across 6 markets          │  │
│  │  • Prediction generation (8 ML models)               │  │
│  │  • Signal alerts with position sizing                │  │
│  │  • Performance tracking and validation               │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘

Data Sources:
├── NOAA National Weather Service (free, 15-min)
├── GOES-16 / GOES-18 Satellite Imagery
├── Sentinel-2 (ESA) Multispectral
├── MODIS Vegetation Indices (NDVI)
├── INMET Brazil Weather Stations
├── Ghana Meteorological Agency
├── CME / ICE Futures Tick Data
└── USDA Crop Reports
```

---

## Key Modules

| File | Description |
|------|-------------|
| `weather_collector.py` | NOAA + satellite data ingestion across all 6 regions |
| `claude_engine.py` | Claude Sonnet AI analysis pipeline |
| `ensemble_predictor.py` | 4-model ML ensemble (RF, GB, Ridge, Lasso) |
| `lstm_predictor.py` | PyTorch LSTM with attention mechanism |
| `backtest.py` | Historical backtesting engine (2023–2025) |
| `config.py` | All system parameters + commodity configuration |
| `correlation_analyzer.py` | Cross-commodity correlation and lead-lag analysis |
| `satellite_data_processor.py` | NDVI, thermal, moisture flux processing |
| `risk_analyzer.py` | Position sizing, stop-loss, drawdown management |
| `volatility_forecaster.py` | GARCH volatility forecasting |
| `market_impact_analyzer.py` | Price impact modeling |
| `microstructure_analyzer.py` | Order flow and market microstructure |
| `database.py` | PostgreSQL data layer |
| `dashboard_api.py` | FastAPI transparency endpoints |
| `main.py` | Main orchestrator |
| `demo.py` | Demo mode with sample data |

---

## Signal Rules

**LONG Signals:**
- NOAA freeze watch/warning in production zone
- Hurricane forecast cone intersects commodity region
- Sustained warm/wet conditions exceeding disease-outbreak thresholds
- Drought index crossing critical threshold (coffee, cocoa, sugar)

**SHORT Signals:**
- Freeze warning cancelled or storm diverts
- Above-average rainfall ends drought
- Crop condition upgrades in USDA weekly reports

**Risk Management:**
- Max 5% portfolio per signal
- 2% stop-loss per position
- Max hold: 21 days
- Average hold time: 4.7 days

---

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export ANTHROPIC_API_KEY=your-key
export NOAA_API_KEY=your-key        # optional
export PLANET_API_KEY=your-key      # optional
export DATABASE_URL=postgresql://localhost/agriquant

# Run demo (no live data required)
python demo.py

# Run full system
python main.py
```

---

## Backtesting

```bash
python backtest.py --start 2023-01-01 --end 2025-12-31 --leverage 2.5
```

Output includes equity curve, per-trade log, Sharpe ratio, max drawdown, and comparison vs. S&P 500 and buy-and-hold futures.

---

## What Worked / What Didn't

**What worked:**
- Freeze warnings with 48+ hour lead time: 75% win rate
- Hurricane path divergence shorts: 85% win rate
- Quick exits after weather event resolves

**What didn't:**
- Trading preliminary model runs (>72 hours out): too early, too noisy
- Holding through USDA report releases: usually priced in by then
- Trading minor cold fronts (<28°F): insufficient crop impact

---

## Disclaimer

Backtested performance uses historical data with 2.5x leverage. Assumes perfect fills, no slippage, and hindsight signal construction. Leverage amplifies both gains and losses. Past performance does not guarantee future results. This is not financial advice.

---

## Links

- Website: [agriquant.ai](https://agriquant.ai)
- Demo: [demo.agriquant.ai](https://demo.agriquant.ai)
- Contact: [hello@agriquant.ai](mailto:hello@agriquant.ai)
- X: [@AgriQuant_AI](https://x.com/AgriQuant_AI)
