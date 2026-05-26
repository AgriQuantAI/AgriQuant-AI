"""
AgriQuant AI - Grains Weather & Data Collector
Corn (ZC/CME): US Corn Belt (Iowa, Illinois, Indiana, Nebraska, Minnesota)
Wheat (ZW/CME): Great Plains (Kansas, Oklahoma, Texas, Colorado)
Primary risks: drought, derecho, early frost, winter kill
"""
import requests, logging
from datetime import datetime
from typing import Dict, List
logger = logging.getLogger(__name__)

CORN_REGIONS = {
    'Iowa': {
        'lat': 42.0, 'lon': -93.6, 'state_fips': '19',
        'production_share': 0.18, 'planting': [4,5], 'pollination': [7],
        'harvest': [9,10,11], 'drought_index_threshold': -2.0, 'priority': 1
    },
    'Illinois': {
        'lat': 40.6, 'lon': -89.2, 'state_fips': '17',
        'production_share': 0.16, 'planting': [4,5], 'pollination': [7],
        'harvest': [9,10,11], 'drought_index_threshold': -2.0, 'priority': 2
    },
    'Nebraska': {
        'lat': 41.5, 'lon': -99.9, 'state_fips': '31',
        'production_share': 0.14, 'planting': [4,5], 'pollination': [7],
        'harvest': [9,10,11], 'drought_index_threshold': -1.8, 'priority': 3
    },
    'Minnesota': {
        'lat': 44.9, 'lon': -93.1, 'state_fips': '27',
        'production_share': 0.09, 'planting': [5], 'pollination': [7,8],
        'harvest': [9,10], 'drought_index_threshold': -1.5, 'priority': 4
    },
    'Indiana': {
        'lat': 40.3, 'lon': -86.1, 'state_fips': '18',
        'production_share': 0.08, 'planting': [4,5], 'pollination': [7],
        'harvest': [9,10,11], 'drought_index_threshold': -2.0, 'priority': 5
    },
}

WHEAT_REGIONS = {
    'Kansas': {
        'lat': 38.7, 'lon': -98.3, 'state_fips': '20',
        'production_share': 0.28, 'type': 'HRW',
        'planting': [9,10], 'harvest': [6,7],
        'winterkill_risk_months': [12,1,2], 'priority': 1
    },
    'Oklahoma': {
        'lat': 35.5, 'lon': -97.5, 'state_fips': '40',
        'production_share': 0.11, 'type': 'HRW',
        'planting': [9,10], 'harvest': [6,7],
        'winterkill_risk_months': [12,1,2], 'priority': 2
    },
    'Texas_Panhandle': {
        'lat': 35.2, 'lon': -101.8, 'state_fips': '48',
        'production_share': 0.09, 'type': 'HRW',
        'planting': [10,11], 'harvest': [6,7],
        'winterkill_risk_months': [1,2], 'priority': 3
    },
    'Washington_SoftWheat': {
        'lat': 46.9, 'lon': -119.1, 'state_fips': '53',
        'production_share': 0.07, 'type': 'SRW',
        'planting': [9,10], 'harvest': [7,8],
        'winterkill_risk_months': [12,1,2,3], 'priority': 4
    },
}

# USDA Crop Progress ratings correlation with price impact
CROP_RATING_IMPACT = {
    # (good_excellent_pct): price_direction, magnitude
    (70, 100): ('bearish', -5),
    (55, 70):  ('neutral', 0),
    (40, 55):  ('bullish', 8),
    (25, 40):  ('bullish', 16),
    (0, 25):   ('strongly_bullish', 28),
}


class GrainsCollector:
    """
    Corn and Wheat weather monitoring across US Corn Belt and Great Plains.
    Sources: NOAA, USDA Crop Progress reports, US Drought Monitor (USDM),
    Climate Prediction Center (CPC) forecasts.
    """

    def __init__(self):
        self.noaa_base = 'https://api.weather.gov'
        self.usda_base = 'https://quickstats.nass.usda.gov/api'
        self.drought_monitor_url = 'https://droughtmonitor.unl.edu/DmData/GISData.aspx'

    def get_state_forecast(self, state: str, lat: float, lon: float) -> Dict:
        """NOAA forecast for a grain production state centroid"""
        try:
            resp = requests.get(f"{self.noaa_base}/points/{lat},{lon}", timeout=10)
            if resp.status_code == 200:
                grid = resp.json()['properties']
                f = requests.get(grid['forecast'], timeout=10)
                hourly = requests.get(grid['forecastHourly'], timeout=10)
                result = {
                    'state': state, 'source': 'NOAA', 'lat': lat, 'lon': lon,
                    'timestamp': datetime.utcnow().isoformat(),
                }
                if f.status_code == 200:
                    result['daily_forecast'] = f.json()['properties']['periods'][:14]
                if hourly.status_code == 200:
                    result['hourly_forecast'] = hourly.json()['properties']['periods'][:48]
                return result
        except Exception as e:
            logger.error(f"Forecast error for {state}: {e}")
        return {'state': state, 'source': 'unavailable', 'timestamp': datetime.utcnow().isoformat()}

    def assess_corn_stress(self, state: str, forecast: Dict,
                           drought_index: float) -> Dict:
        """
        Corn yield stress assessment. Critical periods:
        - Pollination (July): Heat > 95F or drought = yield loss
        - Grain fill (Aug): Moisture needed
        - Spring planting (Apr-May): Cold/wet delays
        """
        region = CORN_REGIONS[state]
        current_month = datetime.utcnow().month
        is_pollination = current_month in region['pollination']
        is_planting = current_month in region['planting']
        is_harvest = current_month in region['harvest']

        stress_score = 0
        signals = []

        # Drought stress
        if drought_index < -3:
            stress_score += 30
            signals.append(f"Exceptional drought (D4): index={drought_index:.1f}")
        elif drought_index < -2:
            stress_score += 20
            signals.append(f"Extreme drought (D3): index={drought_index:.1f}")
        elif drought_index < -1:
            stress_score += 10
            signals.append(f"Severe drought (D2): index={drought_index:.1f}")

        # Pollination heat stress - most critical corn risk
        if is_pollination:
            stress_score *= 1.8
            signals.append("POLLINATION WINDOW: stress multiplied 1.8x")

        price_impact = min(25, stress_score * 0.4)

        return {
            'state': state, 'commodity': 'ZC',
            'drought_index': drought_index,
            'stress_score': round(stress_score, 1),
            'is_pollination_period': is_pollination,
            'is_planting_period': is_planting,
            'signals': signals,
            'estimated_price_impact_pct': round(price_impact, 1),
            'production_share': region['production_share'],
            'signal': 'LONG' if price_impact > 5 else 'NEUTRAL',
            'timestamp': datetime.utcnow().isoformat()
        }

    def assess_wheat_risk(self, state: str, forecast: Dict,
                           drought_index: float) -> Dict:
        """
        Wheat risk assessment.
        HRW wheat: winterkill risk (Jan-Feb), drought at heading (Apr-May),
        heat at grain fill (May-Jun).
        """
        region = WHEAT_REGIONS[state]
        current_month = datetime.utcnow().month
        is_winterkill_risk = current_month in region.get('winterkill_risk_months', [])
        is_harvest = current_month in region['harvest']

        risk_factors = []
        price_impact = 0

        # Drought at heading/grain fill
        if drought_index < -2 and current_month in [4, 5, 6]:
            price_impact += 12
            risk_factors.append(f"Drought at heading: D{abs(int(drought_index))}")

        # Winter kill risk
        if is_winterkill_risk:
            price_impact += 5
            risk_factors.append("Winterkill monitoring period active")

        return {
            'state': state, 'commodity': 'ZW', 'wheat_type': region['type'],
            'drought_index': drought_index,
            'is_winterkill_risk_period': is_winterkill_risk,
            'risk_factors': risk_factors,
            'estimated_price_impact_pct': round(price_impact, 1),
            'production_share': region['production_share'],
            'signal': 'LONG' if price_impact > 4 else 'NEUTRAL',
            'timestamp': datetime.utcnow().isoformat()
        }

    def get_usda_crop_progress(self, commodity: str, state: str) -> Dict:
        """
        Fetch weekly USDA Crop Progress ratings.
        Good/Excellent % is the most-watched ag data point each Monday.
        Drop of 5+ points week-over-week triggers price reaction.
        """
        try:
            params = {
                'key': 'DEMO_KEY',
                'commodity_desc': 'CORN' if commodity == 'ZC' else 'WHEAT',
                'statisticcat_desc': 'CONDITION',
                'state_name': state.upper(),
                'year__GE': str(datetime.utcnow().year - 1),
                'format': 'JSON'
            }
            resp = requests.get(f"{self.usda_base}/api_GET/", params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json().get('data', [])
                good_excellent = [d for d in data
                                  if d.get('unit_desc') in ['GOOD', 'EXCELLENT']]
                return {
                    'commodity': commodity, 'state': state,
                    'crop_progress_data': good_excellent[-8:],
                    'source': 'USDA_NASS',
                    'timestamp': datetime.utcnow().isoformat()
                }
        except Exception as e:
            logger.error(f"USDA crop progress error: {e}")
        return {'commodity': commodity, 'state': state, 'source': 'unavailable'}

    def collect_all_regions(self) -> Dict:
        """Collect all US grain region data"""
        corn_results, wheat_results = {}, {}
        logger.info("Collecting US grains weather data...")

        for state, data in CORN_REGIONS.items():
            forecast = self.get_state_forecast(state, data['lat'], data['lon'])
            drought_idx = -1.5  # placeholder - live: fetch from US Drought Monitor
            stress = self.assess_corn_stress(state, forecast, drought_idx)
            crop_progress = self.get_usda_crop_progress('ZC', state)
            corn_results[state] = {'forecast': forecast, 'stress': stress,
                                   'crop_progress': crop_progress}

        for state, data in WHEAT_REGIONS.items():
            forecast = self.get_state_forecast(state, data['lat'], data['lon'])
            drought_idx = -1.0
            risk = self.assess_wheat_risk(state, forecast, drought_idx)
            crop_progress = self.get_usda_crop_progress('ZW', state)
            wheat_results[state] = {'forecast': forecast, 'risk': risk,
                                    'crop_progress': crop_progress}

        return {
            'timestamp': datetime.utcnow().isoformat(),
            'corn': {'commodity': 'ZC', 'regions': corn_results},
            'wheat': {'commodity': 'ZW', 'regions': wheat_results},
        }
