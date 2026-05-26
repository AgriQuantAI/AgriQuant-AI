"""
AgriQuant AI - Coffee (Arabica) Weather & Data Collector
Region: Minas Gerais, Espirito Santo, Sao Paulo, Brazil
Ticker: KC (ICE)
Primary risks: frost, drought, excessive rainfall
"""

import requests
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from config import COMMODITIES

logger = logging.getLogger(__name__)

# Brazil coffee production regions with INMET station IDs
COFFEE_REGIONS = {
    'Minas_Gerais_Sul': {
        'lat': -21.7, 'lon': -45.9,
        'inmet_station': 'A519',
        'production_share': 0.52,
        'altitude_m': 900,
        'frost_threshold_c': 0,
        'drought_threshold_mm': 20,  # monthly rainfall below this = stress
        'priority': 1
    },
    'Cerrado_Mineiro': {
        'lat': -19.5, 'lon': -46.5,
        'inmet_station': 'A524',
        'production_share': 0.18,
        'altitude_m': 1050,
        'frost_threshold_c': -1,
        'drought_threshold_mm': 25,
        'priority': 2
    },
    'Matas_de_Minas': {
        'lat': -20.8, 'lon': -42.5,
        'inmet_station': 'A537',
        'production_share': 0.15,
        'altitude_m': 700,
        'frost_threshold_c': 2,
        'drought_threshold_mm': 30,
        'priority': 3
    },
    'Espirito_Santo_Conilon': {
        'lat': -19.2, 'lon': -40.3,
        'inmet_station': 'A612',
        'production_share': 0.10,
        'altitude_m': 200,
        'frost_threshold_c': 5,
        'drought_threshold_mm': 35,
        'priority': 4
    },
    'Sao_Paulo_Mogiana': {
        'lat': -20.5, 'lon': -47.4,
        'inmet_station': 'A706',
        'production_share': 0.05,
        'altitude_m': 850,
        'frost_threshold_c': 0,
        'drought_threshold_mm': 20,
        'priority': 5
    },
}

# Historical frost events and KC futures impact
HISTORICAL_FROST_EVENTS = [
    {'date': '2021-07-20', 'region': 'Minas_Gerais_Sul', 'temp_min_c': -3.2, 'kc_impact_pct': 32.5, 'damage': 'severe'},
    {'date': '2021-07-29', 'region': 'Minas_Gerais_Sul', 'temp_min_c': -4.1, 'kc_impact_pct': 18.2, 'damage': 'severe'},
    {'date': '2013-07-05', 'region': 'Cerrado_Mineiro', 'temp_min_c': -1.8, 'kc_impact_pct': 12.4, 'damage': 'moderate'},
    {'date': '2011-07-12', 'region': 'Minas_Gerais_Sul', 'temp_min_c': -2.3, 'kc_impact_pct': 8.7, 'damage': 'moderate'},
    {'date': '2000-08-01', 'region': 'Minas_Gerais_Sul', 'temp_min_c': -5.5, 'kc_impact_pct': 45.3, 'damage': 'catastrophic'},
    {'date': '1994-07-15', 'region': 'Minas_Gerais_Sul', 'temp_min_c': -8.2, 'kc_impact_pct': 62.1, 'damage': 'catastrophic'},
]

# Frost risk calendar - July/August peak season
FROST_RISK_BY_MONTH = {
    1: 0.01, 2: 0.01, 3: 0.00, 4: 0.01, 5: 0.05,
    6: 0.18, 7: 0.35, 8: 0.28, 9: 0.08, 10: 0.02,
    11: 0.01, 12: 0.01
}


class CoffeeBrazilCollector:
    """
    Collects and analyzes weather data for Brazilian Arabica coffee regions.
    Primary data sources: INMET (Brazilian meteorological service),
    CPTEC/INPE forecasts, and NASA SMAP soil moisture.
    """

    def __init__(self):
        self.inmet_base_url = 'https://apitempo.inmet.gov.br'
        self.cptec_base_url = 'https://www.cptec.inpe.br'
        self.noaa_base_url = 'https://api.weather.gov'

    def get_inmet_forecast(self, station_id: str) -> Dict:
        """
        Fetch forecast from INMET (Instituto Nacional de Meteorologia)
        Brazil's national meteorological service
        """
        try:
            url = f"{self.inmet_base_url}/estacao/{station_id}"
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                return {
                    'station_id': station_id,
                    'timestamp': datetime.utcnow().isoformat(),
                    'temp_min_c': data.get('TempMinima'),
                    'temp_max_c': data.get('TempMaxima'),
                    'temp_current_c': data.get('TempAr'),
                    'humidity_pct': data.get('UmidadeRelAr'),
                    'rainfall_mm': data.get('Chuva'),
                    'wind_speed_ms': data.get('VelocidadeVento'),
                    'source': 'INMET'
                }
            else:
                logger.warning(f"INMET returned {response.status_code} for station {station_id}")
                return self._get_gfs_fallback(station_id)

        except Exception as e:
            logger.error(f"INMET fetch error for {station_id}: {e}")
            return self._get_gfs_fallback(station_id)

    def _get_gfs_fallback(self, station_id: str) -> Dict:
        """
        Fallback to NOAA GFS model data when INMET is unavailable.
        GFS provides global coverage including Brazil with 0.25deg resolution.
        """
        region = next((r for r, d in COFFEE_REGIONS.items()
                      if d['inmet_station'] == station_id), None)
        if not region:
            return {}

        region_data = COFFEE_REGIONS[region]
        lat, lon = region_data['lat'], region_data['lon']

        try:
            points_url = f"{self.noaa_base_url}/points/{lat},{lon}"
            response = requests.get(points_url, timeout=10)
            if response.status_code == 200:
                grid_data = response.json()
                forecast_url = grid_data['properties']['forecast']
                forecast_resp = requests.get(forecast_url, timeout=10)
                if forecast_resp.status_code == 200:
                    periods = forecast_resp.json()['properties']['periods']
                    return {
                        'station_id': station_id,
                        'source': 'NOAA_GFS_fallback',
                        'timestamp': datetime.utcnow().isoformat(),
                        'forecast_periods': periods[:8]
                    }
        except Exception as e:
            logger.error(f"GFS fallback error: {e}")

        return {'station_id': station_id, 'source': 'unavailable'}

    def assess_frost_risk(self, region_name: str, forecast_data: Dict) -> Dict:
        """
        Assess frost risk for a Brazilian coffee region.
        Frost below 0C causes leaf damage; below -2C causes branch kill;
        below -4C causes permanent tree death (multi-year supply impact).
        """
        region = COFFEE_REGIONS[region_name]
        current_month = datetime.utcnow().month
        base_risk = FROST_RISK_BY_MONTH[current_month]

        temp_min = forecast_data.get('temp_min_c')
        if temp_min is None:
            return {'risk_level': 'unknown', 'base_probability': base_risk}

        # Frost damage tiers
        if temp_min <= -4:
            damage_tier = 'catastrophic'  # Tree death, 2-3 year supply impact
            price_impact_range = (40, 65)
        elif temp_min <= -2:
            damage_tier = 'severe'         # Branch kill, 1-2 year impact
            price_impact_range = (20, 40)
        elif temp_min <= 0:
            damage_tier = 'moderate'       # Leaf scorch, current crop damage
            price_impact_range = (8, 20)
        elif temp_min <= region['frost_threshold_c']:
            damage_tier = 'minor'
            price_impact_range = (2, 8)
        else:
            damage_tier = 'none'
            price_impact_range = (0, 0)

        # Altitude adjustment: higher altitude = more frost-prone
        altitude_factor = min(1.5, region['altitude_m'] / 800)

        return {
            'region': region_name,
            'temp_min_forecast_c': temp_min,
            'damage_tier': damage_tier,
            'base_monthly_risk': base_risk,
            'altitude_factor': altitude_factor,
            'adjusted_probability': min(0.95, base_risk * altitude_factor),
            'price_impact_range_pct': price_impact_range,
            'production_share': region['production_share'],
            'historical_analogs': self._find_historical_analogs(temp_min, current_month),
            'timestamp': datetime.utcnow().isoformat()
        }

    def assess_drought_risk(self, region_name: str, rainfall_data: Dict) -> Dict:
        """
        Assess drought risk - critical during flowering (Oct-Dec) and
        fruit development (Jan-Mar). El Nino years increase risk significantly.
        """
        region = COFFEE_REGIONS[region_name]
        monthly_rainfall = rainfall_data.get('monthly_total_mm', 0)
        threshold = region['drought_threshold_mm']

        deficit = max(0, threshold - monthly_rainfall)
        deficit_pct = deficit / threshold if threshold > 0 else 0

        if deficit_pct > 0.7:
            risk_level = 'critical'
            price_impact_range = (15, 35)
        elif deficit_pct > 0.4:
            risk_level = 'high'
            price_impact_range = (8, 18)
        elif deficit_pct > 0.2:
            risk_level = 'moderate'
            price_impact_range = (3, 10)
        else:
            risk_level = 'low'
            price_impact_range = (0, 3)

        return {
            'region': region_name,
            'monthly_rainfall_mm': monthly_rainfall,
            'threshold_mm': threshold,
            'deficit_mm': deficit,
            'deficit_pct': deficit_pct,
            'risk_level': risk_level,
            'price_impact_range_pct': price_impact_range,
            'production_share': region['production_share'],
            'timestamp': datetime.utcnow().isoformat()
        }

    def _find_historical_analogs(self, temp_min_c: float,
                                  month: int) -> List[Dict]:
        """Find historical frost events with similar temperature profiles"""
        analogs = []
        for event in HISTORICAL_FROST_EVENTS:
            event_month = int(event['date'].split('-')[1])
            temp_diff = abs(event['temp_min_c'] - temp_min_c)
            if event_month == month and temp_diff <= 1.5:
                analogs.append(event)
        return sorted(analogs, key=lambda x: abs(x['temp_min_c'] - temp_min_c))[:3]

    def collect_all_regions(self) -> Dict:
        """
        Collect weather data for all Brazilian coffee regions.
        Called every 15 minutes by main orchestrator.
        """
        results = {}
        logger.info("Collecting Brazil coffee region weather data...")

        for region_name, region_data in COFFEE_REGIONS.items():
            station_id = region_data['inmet_station']
            forecast = self.get_inmet_forecast(station_id)
            frost_risk = self.assess_frost_risk(region_name, forecast)

            rainfall_data = {'monthly_total_mm': forecast.get('rainfall_mm', 0) * 30}
            drought_risk = self.assess_drought_risk(region_name, rainfall_data)

            results[region_name] = {
                'forecast': forecast,
                'frost_risk': frost_risk,
                'drought_risk': drought_risk,
                'priority': region_data['priority']
            }
            logger.info(f"  {region_name}: frost={frost_risk['damage_tier']}, "
                       f"drought={drought_risk['risk_level']}")

        return {
            'commodity': 'KC',
            'timestamp': datetime.utcnow().isoformat(),
            'regions': results,
            'aggregate_frost_risk': self._aggregate_frost_risk(results),
            'aggregate_drought_risk': self._aggregate_drought_risk(results)
        }

    def _aggregate_frost_risk(self, results: Dict) -> Dict:
        """Weight frost risks by production share"""
        weighted_impact = 0
        for region_name, data in results.items():
            share = COFFEE_REGIONS[region_name]['production_share']
            impact_mid = sum(data['frost_risk'].get('price_impact_range_pct', (0,0))) / 2
            weighted_impact += share * impact_mid

        return {
            'weighted_price_impact_pct': round(weighted_impact, 2),
            'signal': 'LONG' if weighted_impact > 5 else 'NEUTRAL'
        }

    def _aggregate_drought_risk(self, results: Dict) -> Dict:
        """Weight drought risks by production share"""
        weighted_impact = 0
        for region_name, data in results.items():
            share = COFFEE_REGIONS[region_name]['production_share']
            impact_mid = sum(data['drought_risk'].get('price_impact_range_pct', (0,0))) / 2
            weighted_impact += share * impact_mid

        return {
            'weighted_price_impact_pct': round(weighted_impact, 2),
            'signal': 'LONG' if weighted_impact > 5 else 'NEUTRAL'
        }
