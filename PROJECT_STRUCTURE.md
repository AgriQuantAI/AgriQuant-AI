# AgriQuant AI - Project Structure

## File Overview

```
agriquant/
│
├── README.md                 # Complete documentation and setup guide
├── requirements.txt          # Python dependencies
│
├── config.py                # System configuration and parameters
│   • API keys and credentials
│   • Geographic parameters (Florida counties)
│   • Weather thresholds (freeze, hurricane, disease)
│   • Prediction thresholds and confidence levels
│   • Academic research model parameters
│   • Database configuration
│   • Logging and monitoring settings
│   • Feature flags
│
├── weather_collector.py     # NOAA weather data collection
│   • NOAAWeatherCollector class
│   • Fetch forecasts for production regions
│   • Detect freeze risk from temperature data
│   • Hurricane threat monitoring
│   • Ensemble forecasting (GFS, NAM, HRRR models)
│   • Historical analog matching
│
├── claude_engine.py         # Claude Sonnet 4 AI analysis
│   • ClaudeAnalysisEngine class
│   • Freeze event analysis
│   • Hurricane threat analysis
│   • Disease pressure analysis
│   • Prediction quality validation
│   • Generate user-friendly explanations
│
├── database.py              # PostgreSQL database operations
│   • AgriQuant AIDatabase class
│   • Store weather forecasts
│   • Store AI predictions
│   • Store historical events (40 years)
│   • Store USDA reports
│   • Track performance metrics
│   • Verify predictions against actual outcomes
│
├── main.py                  # Main orchestration system
│   • AgriQuant AIOrchestrator class
│   • Coordinate all components
│   • Run monitoring cycles (every 15 min)
│   • Generate predictions when thresholds met
│   • Send high-confidence alerts
│   • Verify predictions against USDA data
│   • Generate performance reports
│   • Continuous monitoring mode
│
├── backtest.py              # Historical validation
│   • AgriQuant AIBacktest class
│   • Test prediction accuracy on past data
│   • Load historical events from database
│   • Simulate forecasts N days before events
│   • Compare predictions to actual outcomes
│   • Calculate accuracy metrics
│   • Confidence calibration analysis
│
└── demo.py                  # Quick demonstration script
    • Show complete workflow
    • Weather data collection demo
    • AI prediction generation demo
    • Database storage walkthrough
    • Performance tracking overview
```

## Component Responsibilities

### 1. Configuration (config.py)
**Purpose:** Central configuration for all system parameters

**Key Constants:**
- `CITRUS_COUNTIES` - Geographic data for 4 main counties
- `FREEZE_THRESHOLDS` - Temperature/duration combinations for damage levels
- `MIN_CONFIDENCE_THRESHOLD` - Minimum 70% to generate prediction
- `ANTHROPIC_API_KEY` - Claude Sonnet 4 API access
- `DATABASE_URL` - PostgreSQL connection string

**When to modify:**
- Change threshold sensitivity
- Add new counties to monitor
- Update API credentials
- Adjust polling intervals

---

### 2. Weather Collection (weather_collector.py)
**Purpose:** Interface with NOAA APIs and weather data sources

**Main Class:** `NOAAWeatherCollector`

**Key Methods:**
- `get_forecast_for_county(county_name)` → Dict
  - Fetches complete forecast for one county
  - Returns hourly + daily forecasts + alerts
  
- `detect_freeze_risk(forecast)` → Dict
  - Analyzes temperature data
  - Identifies freeze severity level
  - Calculates expected duration
  
- `detect_hurricane_threat(county_name)` → List
  - Checks National Hurricane Center
  - Returns active storms threatening region
  
- `get_ensemble_forecast(county_name)` → Dict
  - Combines multiple weather models
  - Returns consensus with agreement score
  
- `monitor_all_counties()` → Dict
  - Main monitoring function
  - Checks all 4 counties
  - Returns aggregate risk assessment

**Data Sources:**
- weather.gov (NOAA forecasts)
- nhc.noaa.gov (hurricanes)
- Free APIs, no authentication required

**Typical Usage:**
```python
collector = NOAAWeatherCollector()
forecast = collector.get_ensemble_forecast('Polk')
freeze_risk = forecast['freeze_risk']
if freeze_risk['risk'] != 'none':
    # Trigger AI analysis
```

---

### 3. AI Analysis Engine (claude_engine.py)
**Purpose:** Generate predictions using Claude Sonnet 4

**Main Class:** `ClaudeAnalysisEngine`

**Key Methods:**
- `analyze_freeze_event(forecast, historical_analogs)` → Dict
  - Main prediction function
  - Takes weather forecast + historical similar events
  - Returns structured JSON prediction
  
- `analyze_hurricane_threat(forecast, hurricane_data)` → Dict
  - Hurricane-specific analysis
  - Direct hit vs. near miss scenarios
  
- `analyze_disease_pressure(forecast, weather_pattern)` → Dict
  - Disease outbreak prediction
  - Based on Li et al. (2020) research
  
- `validate_prediction_quality(prediction)` → Dict
  - Meta-analysis of prediction
  - AI reviews its own output
  - Identifies weaknesses
  
- `explain_prediction_to_user(prediction)` → str
  - Convert technical prediction to plain English
  - For public communications

**Prediction Structure:**
```json
{
  "prediction_id": "PRED_Polk_20260201_...",
  "probability": 0.82,
  "expected_crop_damage_pct": 0.135,
  "confidence_score": 0.85,
  "timing": {"onset": "...", "duration_hours": 5},
  "reasoning": "Step-by-step analysis...",
  "key_factors": ["Arctic air mass", "Drought stress"],
  "uncertainties": ["Wind speed variation"]
}
```

**Typical Usage:**
```python
engine = ClaudeAnalysisEngine()
prediction = engine.analyze_freeze_event(
    forecast_data=forecast,
    historical_analogs=[...similar events...]
)
```

---

### 4. Database (database.py)
**Purpose:** PostgreSQL storage and retrieval

**Main Class:** `AgriQuant AIDatabase`

**Database Tables:**
- `weather_forecasts` - All NOAA forecasts collected
- `ai_predictions` - All predictions generated
- `historical_events` - 40 years of verified events
- `usda_reports` - Official crop damage reports
- `satellite_imagery` - Planet Labs / Sentinel-2 metadata
- `market_prices` - CME agricultural commodity futures
- `performance_metrics` - Daily accuracy tracking

**Key Methods:**
- `store_weather_forecast(forecast)` → int (ID)
- `store_ai_prediction(prediction)` → int (ID)
- `verify_prediction(prediction_id, actual_damage)` → bool
- `get_prediction_performance(start_date, end_date)` → Dict
- `get_historical_analogs(event_type, temperature)` → List

**Performance Tracking:**
```python
metrics = db.get_prediction_performance()
# Returns:
{
  'total_predictions': 23,
  'verified_count': 16,
  'avg_accuracy': 0.73,
  'success_rate': 0.70
}
```

**Typical Usage:**
```python
db = AgriQuant AIDatabase()
db.connect()
pred_id = db.store_ai_prediction(prediction)
# Later, when USDA report available:
db.verify_prediction(pred_id, actual_damage=0.127, 
                     verification_source='USDA Report')
```

---

### 5. Main Orchestrator (main.py)
**Purpose:** Coordinate entire system workflow

**Main Class:** `AgriQuant AIOrchestrator`

**Workflow:**
```
Every 15 minutes:
  → Collect weather forecasts (all counties)
  → Check for freeze/hurricane risk
  → If risk detected AND thresholds met:
      → Query historical analogs
      → Generate AI prediction
      → Store in database
      → Send alert if high confidence
  → Log results

Daily at 9:00 AM:
  → Check for new USDA reports
  → Verify pending predictions
  → Update accuracy metrics

Weekly on Monday:
  → Generate performance report
  → Email to team
```

**Run Modes:**
- `python main.py once` - Single monitoring cycle (testing)
- `python main.py continuous` - 24/7 operation (production)
- `python main.py report` - Generate performance report
- `python main.py verify` - Manual prediction verification

**Typical Production Usage:**
```bash
# Start as background service
screen -S agriquant
python main.py continuous
# Detach with Ctrl+A, D

# Check logs
tail -f /var/log/agriquant/main.log
```

---

### 6. Backtesting (backtest.py)
**Purpose:** Validate prediction accuracy on historical data

**Main Class:** `AgriQuant AIBacktest`

**Process:**
1. Load historical events (2023-2025)
2. For each event:
   - Simulate forecast 3 days before
   - Generate AI prediction
   - Compare to actual USDA-verified outcome
3. Calculate metrics:
   - Mean accuracy
   - Success rate (±5 percentage points)
   - False positive/negative rates
   - Confidence calibration

**Usage:**
```bash
python backtest.py --start 2023-01-01 --end 2025-12-31 --output results.json
```

**Example Output:**
```
Total Events: 23
Predictions Generated: 23
Verified: 23

Mean Accuracy: 73.2%
Success Rate: 70%
MAE: 2.4 percentage points

Freeze events: 75% accuracy (8 events)
Hurricane threats: 71% accuracy (7 events)
Disease pressure: 60% accuracy (5 events)
```

---

### 7. Demo Script (demo.py)
**Purpose:** Quick demonstration without full setup

**Functions:**
- `demo_weather_collection()` - Show NOAA data retrieval
- `demo_ai_analysis()` - Show Claude prediction generation
- `demo_database_storage()` - Explain database schema
- `demo_performance_tracking()` - Show metrics

**Usage:**
```bash
python demo.py
```

**No prerequisites required** - runs with mock data if APIs unavailable

---

## Data Flow

```
┌─────────────────┐
│   NOAA APIs     │
│  (weather.gov)  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────┐
│   weather_collector.py      │
│  • Fetch forecasts          │
│  • Detect freeze risk       │
│  • Check hurricanes         │
└────────┬────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│      main.py                │
│  • Check thresholds         │
│  • Query historical data    │
└────────┬────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│    claude_engine.py         │
│  • Analyze with AI          │
│  • Generate prediction      │
└────────┬────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│     database.py             │
│  • Store prediction         │
│  • Track for verification   │
└────────┬────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│   (7-14 days later)         │
│   USDA Report Published     │
└────────┬────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│     database.py             │
│  • Verify prediction        │
│  • Calculate accuracy       │
│  • Update metrics           │
└─────────────────────────────┘
```

---

## Quick Start Commands

```bash
# 1. Setup
pip install -r requirements.txt
export ANTHROPIC_API_KEY='your-key'
export DATABASE_URL='postgresql://localhost/agriquant'

# 2. Initialize database
python -c "from database import *; db=AgriQuant AIDatabase(); db.connect(); db.create_tables(); db.seed_historical_data()"

# 3. Run demo
python demo.py

# 4. Test single cycle
python main.py once

# 5. Start production monitoring
python main.py continuous

# 6. Run backtest
python backtest.py --start 2023-01-01 --end 2025-12-31
```

---

## Monitoring in Production

```bash
# System status
systemctl status agriquant

# View logs
tail -f /var/log/agriquant/main.log

# Check recent predictions
psql agriquant -c "SELECT prediction_id, county, expected_damage_pct, confidence_score FROM ai_predictions ORDER BY prediction_time DESC LIMIT 10;"

# Performance metrics
python main.py report
```

---

## Troubleshooting

**Issue:** No predictions generated
- Check `MIN_CONFIDENCE_THRESHOLD` in config.py (try lowering to 0.60)
- Check `MIN_MODEL_AGREEMENT` (try lowering to 0.70)
- Verify NOAA API is accessible: `curl https://api.weather.gov`

**Issue:** Claude API errors
- Check ANTHROPIC_API_KEY is set correctly
- Verify rate limits in config.py
- Check account credits at console.anthropic.com

**Issue:** Database connection failed
- Verify PostgreSQL is running: `systemctl status postgresql`
- Check DATABASE_URL format: `postgresql://user:pass@host/db`
- Create database: `createdb agriquant`

---

## Code Metrics

- **Total Lines:** ~3,500 lines of Python
- **Test Coverage:** Unit tests in tests/ directory
- **API Calls per Day:** ~96 NOAA requests, ~10 Claude requests
- **Database Size:** ~1GB for 1 year of data
- **Processing Time:** 2-3 seconds per prediction

---

## License & Credits

**License:** MIT

**Built with:**
- Claude Sonnet 4 (Anthropic)
- NOAA National Weather Service
- PostgreSQL
- Python 3.9+

**Research:**
- Singerman et al. (2018) - UF/IFAS
- Li et al. (2020) - UF/IFAS

---

**For full documentation, see README.md**
