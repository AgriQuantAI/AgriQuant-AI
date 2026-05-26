"""
AgriQuant AI - Configuration File
All system parameters, API keys, and thresholds
"""

import os
from datetime import datetime

# ============================================================================
# API CREDENTIALS
# ============================================================================

# Anthropic API (Claude Sonnet 4)
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', 'your-api-key-here')
CLAUDE_MODEL = 'claude-sonnet-4-20250514'

# NOAA API (free, no key required for most endpoints)
NOAA_API_KEY = os.getenv('NOAA_API_KEY', '')  # Optional, increases rate limits
NOAA_BASE_URL = 'https://api.weather.gov'

# Planet Labs API (satellite imagery - paid)
PLANET_API_KEY = os.getenv('PLANET_API_KEY', 'your-planet-key-here')

# CME Data Feed (market data - paid)
CME_API_KEY = os.getenv('CME_API_KEY', 'your-cme-key-here')

# Database
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://localhost/agriquant')

# ============================================================================
# GEOGRAPHIC PARAMETERS - Multi-Commodity Agricultural Regions
# ============================================================================

# Primary citrus producing counties
# Florida OJ / Citrus regions
CITRUS_COUNTIES = {
    'Polk': {
        'fips': '12105',
        'production_share': 0.35,  # 35% of FL production
        'lat': 28.0,
        'lon': -81.8,
        'priority': 1
    },
    'Highlands': {
        'fips': '12055',
        'production_share': 0.20,
        'lat': 27.5,
        'lon': -81.3,
        'priority': 2
    },
    'Hardee': {
        'fips': '12049',
        'production_share': 0.10,
        'lat': 27.5,
        'lon': -81.8,
        'priority': 3
    },
    'DeSoto': {
        'fips': '12027',
        'production_share': 0.05,
        'lat': 27.2,
        'lon': -81.8,
        'priority': 4
    }
}

# Citrus belt bounding box (for satellite imagery)
FLORIDA_BBOX = {
    'min_lat': 26.5,
    'max_lat': 28.5,
    'min_lon': -82.5,
    'max_lon': -80.5
}

# ============================================================================
# WEATHER THRESHOLDS - Critical Damage Levels
# ============================================================================

# Freeze damage thresholds (Fahrenheit)
FREEZE_THRESHOLDS = {
    'light_damage': {
        'temp': 28.0,
        'duration_hours': 2,
        'damage_pct': 0.03  # 3% crop loss
    },
    'moderate_damage': {
        'temp': 26.0,
        'duration_hours': 4,
        'damage_pct': 0.08  # 8% crop loss
    },
    'severe_damage': {
        'temp': 24.0,
        'duration_hours': 4,
        'damage_pct': 0.15  # 15% crop loss
    },
    'catastrophic_damage': {
        'temp': 20.0,
        'duration_hours': 6,
        'damage_pct': 0.30  # 30% crop loss
    }
}

# Hurricane thresholds
HURRICANE_THRESHOLDS = {
    'tropical_storm': {
        'wind_mph': 39,
        'damage_pct': 0.05
    },
    'category_1': {
        'wind_mph': 74,
        'damage_pct': 0.10
    },
    'category_2': {
        'wind_mph': 96,
        'damage_pct': 0.18
    },
    'category_3': {
        'wind_mph': 111,
        'damage_pct': 0.30
    }
}

# Disease pressure (crop disease)
DISEASE_THRESHOLDS = {
    'favorable_conditions': {
        'temp_min': 85.0,  # Fahrenheit
        'temp_max': 95.0,
        'humidity_min': 70.0,  # Percent
        'consecutive_days': 10,
        'damage_pct': 0.06  # 6% additional crop loss over 6 months
    }
}

# Drought thresholds
DROUGHT_THRESHOLDS = {
    'moderate': {
        'days_no_rain': 30,
        'soil_moisture_pct': 40,
        'stress_multiplier': 1.10  # 10% more vulnerable to other events
    },
    'severe': {
        'days_no_rain': 60,
        'soil_moisture_pct': 25,
        'stress_multiplier': 1.20  # 20% more vulnerable
    }
}

# ============================================================================
# PREDICTION THRESHOLDS
# ============================================================================

# Minimum confidence to generate a forecast
MIN_CONFIDENCE_THRESHOLD = 0.70  # 70%

# Minimum expected impact to generate signal
MIN_EXPECTED_IMPACT = 0.05  # 5% crop damage

# Model agreement threshold (ensemble forecasting)
MIN_MODEL_AGREEMENT = 0.75  # 3 out of 4 models must agree

# Forecast time windows (hours ahead)
FORECAST_WINDOWS = {
    'immediate': 24,      # 0-24 hours (highest confidence)
    'short_term': 72,     # 24-72 hours (high confidence)
    'medium_term': 168,   # 72-168 hours (moderate confidence)
    'long_term': 336      # 168-336 hours (lower confidence)
}

# Confidence degradation by forecast window
CONFIDENCE_DECAY = {
    'immediate': 1.0,     # No decay
    'short_term': 0.95,   # 5% reduction
    'medium_term': 0.85,  # 15% reduction
    'long_term': 0.70     # 30% reduction
}

# ============================================================================
# DATA COLLECTION PARAMETERS
# ============================================================================

# How often to poll each data source (seconds)
POLLING_INTERVALS = {
    'noaa_forecast': 900,      # 15 minutes
    'noaa_satellite': 600,     # 10 minutes
    'hurricane_center': 3600,  # 1 hour (or on-demand during active storms)
    'usda_reports': 86400,     # Daily
    'planet_imagery': 86400,   # Daily
    'cme_prices': 300          # 5 minutes during trading hours
}

# Historical data depth
HISTORICAL_DATA_YEARS = 40  # Back to 1984

# Maximum API retry attempts
MAX_API_RETRIES = 3
API_RETRY_DELAY = 5  # seconds

# ============================================================================
# AI MODEL PARAMETERS
# ============================================================================

# Claude Sonnet 4 settings
CLAUDE_SETTINGS = {
    'model': CLAUDE_MODEL,
    'max_tokens': 4000,
    'temperature': 0.1,  # Low temperature for consistent, factual output
    'timeout': 60  # seconds
}

# System prompt for weather analysis
SYSTEM_PROMPT = """You are AgriQuant AI, a specialized system for predicting agricultural commodity price impacts from weather events across six global markets: Orange Juice (Florida), Coffee (Brazil), Cocoa (West Africa), Sugar (Brazil/India), Corn (US Midwest), and Wheat (Great Plains/Black Sea). You analyze satellite data, weather forecasts, and 40 years of weather-price correlations to generate signals 48-72 hours before traditional analysts react.

Your expertise:
- Meteorology and weather pattern analysis
- Agricultural economics and crop damage assessment
- Historical weather-yield correlation analysis
- Probabilistic forecasting

You analyze NOAA weather forecasts, cross-reference with 40 years of historical data, and generate precise crop damage predictions.

Always:
1. Calculate probabilities, not certainties
2. Reference specific historical precedents
3. Quantify expected crop damage percentage
4. Assign confidence scores
5. Explain your reasoning step-by-step

Never:
1. Make binary predictions without probabilities
2. Ignore model disagreement
3. Predict beyond weather forecasts (you use NOAA data, not independent predictions)
4. Override systematic rules
"""

# ============================================================================
# ACADEMIC RESEARCH MODELS
# ============================================================================

# Singerman et al. (2018) regression coefficients
# Economic impact of freeze by temperature and duration
SINGERMAN_FREEZE_MODEL = {
    'base_damage': 0.02,  # 2% baseline
    'temp_coefficient': -0.004,  # Per degree below 32°F
    'duration_coefficient': 0.015,  # Per hour of freeze
    'interaction_term': -0.0005  # Temp × Duration interaction
}

# Li et al. (2020) disease pressure model
# Weather correlation with Asian citrus psyllid population
LI_DISEASE_MODEL = {
    'temp_optimal': 90.0,  # °F for psyllid reproduction
    'temp_coefficient': -0.003,  # Per degree deviation from optimal
    'humidity_coefficient': 0.002,  # Per % humidity
    'duration_coefficient': 0.01,  # Per consecutive day
    'max_impact': 0.08  # 8% maximum crop loss per season
}

# Spatial propagation model
# How localized freeze spreads across agricultural production zones
SPATIAL_PROPAGATION = {
    'polk_to_highlands': 0.85,  # 85% correlation
    'polk_to_hardee': 0.75,
    'polk_to_desoto': 0.65,
    'distance_decay': 0.05  # Per 10 miles
}

# ============================================================================
# TIMING PARAMETERS
# ============================================================================

# Seasonal vulnerability (by month)
# January = peak fruit on trees, maximum vulnerability
SEASONAL_VULNERABILITY = {
    1: 1.00,  # January - peak
    2: 0.95,  # February - high
    3: 0.70,  # March - moderate
    4: 0.40,  # April - low
    5: 0.10,  # May - minimal
    6: 0.05,  # June - bloom
    7: 0.05,  # July - fruit set
    8: 0.10,  # August - early growth
    9: 0.20,  # September - growth
    10: 0.40, # October - pre-harvest
    11: 0.70, # November - approaching harvest
    12: 0.90  # December - harvest season
}

# USDA report lag times (days after event)
USDA_REPORT_LAGS = {
    'freeze': 14,      # 2 weeks
    'hurricane': 10,   # 10 days
    'disease': 21,     # 3 weeks
    'drought': 30      # 1 month
}

# ============================================================================
# DATABASE SCHEMA
# ============================================================================

# Table names
TABLES = {
    'weather_forecasts': 'weather_forecasts',
    'historical_events': 'historical_events',
    'ai_predictions': 'ai_predictions',
    'usda_reports': 'usda_reports',
    'satellite_imagery': 'satellite_imagery',
    'market_prices': 'market_prices',
    'performance_metrics': 'performance_metrics'
}

# ============================================================================
# LOGGING & MONITORING
# ============================================================================

# Log levels
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# Log file locations
LOG_FILES = {
    'main': '/var/log/agriquant/main.log',
    'api': '/var/log/agriquant/api.log',
    'predictions': '/var/log/agriquant/predictions.log',
    'errors': '/var/log/agriquant/errors.log'
}

# Alert thresholds
ALERT_THRESHOLDS = {
    'api_failure_count': 5,      # Alert if 5 consecutive API failures
    'prediction_confidence': 0.85, # Alert if high confidence prediction
    'data_staleness': 3600       # Alert if data older than 1 hour
}

# ============================================================================
# VALIDATION PARAMETERS
# ============================================================================

# Out-of-sample testing
VALIDATION_SPLIT = {
    'train': 0.70,      # 70% training data (2023-early 2025)
    'validate': 0.15,   # 15% validation (mid-2025)
    'test': 0.15        # 15% test (late 2025)
}

# Backtesting parameters
BACKTEST_START_DATE = datetime(2023, 1, 1)
BACKTEST_END_DATE = datetime(2025, 12, 31)

# Accuracy metrics to track
METRICS_TO_TRACK = [
    'forecast_accuracy',      # % of predictions verified by USDA
    'mean_absolute_error',    # Average % error in damage estimates
    'directional_accuracy',   # % correct on damage vs. no damage
    'confidence_calibration', # Are 80% confidence predictions right 80% of time?
    'false_positive_rate',
    'false_negative_rate'
]

# ============================================================================
# SYSTEM STATUS
# ============================================================================

# Current deployment phase
DEPLOYMENT_PHASE = os.getenv('DEPLOYMENT_PHASE', 'PAPER_TRADING')  # PAPER_TRADING, LIVE

# System start date
SYSTEM_START_DATE = datetime(2026, 1, 1)

# Contact information
CONTACT = {
    'email': 'research@agriquant.ai',
    'github': 'github.com/agriquant',
    'website': 'agriquant.ai'
}

# Version
VERSION = '1.0.0'
BUILD_DATE = datetime.now().isoformat()

# ============================================================================
# FEATURE FLAGS
# ============================================================================

FEATURES = {
    'enable_real_time_monitoring': True,
    'enable_ai_predictions': True,
    'enable_satellite_imagery': True,
    'enable_hurricane_tracking': True,
    'enable_disease_monitoring': True,
    'enable_ensemble_forecasting': True,
    'enable_performance_tracking': True,
    'enable_alerts': True,
    'enable_api_caching': True,
    'enable_backtesting': False  # Set to True when running historical validation
}

# ============================================================================
# RATE LIMITS
# ============================================================================

RATE_LIMITS = {
    'anthropic_rpm': 50,        # Requests per minute
    'noaa_rpm': 300,
    'planet_daily': 1000,       # API calls per day
    'cme_rpm': 60
}

print(f"AgriQuant AI Config Loaded - Version {VERSION}")
print(f"Deployment Phase: {DEPLOYMENT_PHASE}")
print(f"Claude Model: {CLAUDE_MODEL}")

# ============================================================================
# MULTI-COMMODITY CONFIGURATION
# ============================================================================

COMMODITIES = {
    'OJ': {
        'name': 'Orange Juice',
        'ticker': 'FCOJ-A',
        'exchange': 'ICE',
        'region': 'Florida, USA',
        'primary_risk': 'freeze, hurricane, citrus greening',
        'bbox': {'lat_min': 25.5, 'lat_max': 30.5, 'lon_min': -83.0, 'lon_max': -79.5},
    },
    'KC': {
        'name': 'Coffee (Arabica)',
        'ticker': 'KC',
        'exchange': 'ICE',
        'region': 'Minas Gerais, Brazil',
        'primary_risk': 'frost, drought, excessive rain',
        'bbox': {'lat_min': -25.0, 'lat_max': -14.0, 'lon_min': -50.0, 'lon_max': -38.0},
    },
    'CC': {
        'name': 'Cocoa',
        'ticker': 'CC',
        'exchange': 'ICE',
        'region': 'Ghana / Ivory Coast',
        'primary_risk': 'drought, Harmattan winds, disease',
        'bbox': {'lat_min': 4.0, 'lat_max': 11.0, 'lon_min': -8.0, 'lon_max': 2.0},
    },
    'SB': {
        'name': 'Sugar #11',
        'ticker': 'SB',
        'exchange': 'ICE',
        'region': 'Brazil / India',
        'primary_risk': 'drought, monsoon failure, policy',
        'bbox': {'lat_min': -25.0, 'lat_max': -14.0, 'lon_min': -52.0, 'lon_max': -38.0},
    },
    'ZC': {
        'name': 'Corn',
        'ticker': 'ZC',
        'exchange': 'CME',
        'region': 'US Midwest',
        'primary_risk': 'drought, derecho, early frost',
        'bbox': {'lat_min': 36.0, 'lat_max': 48.0, 'lon_min': -104.0, 'lon_max': -80.0},
    },
    'ZW': {
        'name': 'Wheat',
        'ticker': 'ZW',
        'exchange': 'CME',
        'region': 'Great Plains / Black Sea',
        'primary_risk': 'drought, freeze, Black Sea disruption',
        'bbox': {'lat_min': 34.0, 'lat_max': 49.0, 'lon_min': -105.0, 'lon_max': -94.0},
    },
}

# Active commodities to monitor
ACTIVE_COMMODITIES = ['OJ', 'KC', 'CC', 'SB', 'ZC', 'ZW']
