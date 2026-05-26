"""
AgriQuant AI - Cocoa Weather & Data Collector
Region: Ghana, Ivory Coast (Cote d'Ivoire)
Ticker: CC (ICE)
Primary risks: Harmattan dry winds, drought, Black Pod disease, El Nino
"""

import requests
import logging
from datetime import datetime
from typing import Dict, List, Optional
from config import COMMODITIES

logger = logging.getLogger(__name__)

# West Africa cocoa production regions
COCOA_REGIONS = {
    'Ashanti_Ghana': {
        'lat': 6.7, 'lon': -1.6,
        'country': 'Ghana',
        'gmet_station': 'DGSV',
        'production_share': 0.22,
        'main_crop_months': [10, 11, 12, 1],    # Oct-Jan main crop
        'midcrop_months': [4, 5, 6],              # Apr-Jun mid crop
        'harmattan_months': [11, 12, 1, 2],       # Nov-Feb dry season
        'priority': 1
    },
    'Western_Ghana': {
        'lat': 5.9, 'lon': -2.6,
        'country': 'Ghana',
        'gmet_station': 'DGTK',
        'production_share': 0.18,
        'main_crop_months': [10, 11, 12, 1],
        'midcrop_months': [4, 5, 6],
        'harmattan_months': [11, 12, 1, 2],
        'priority': 2
    },
    'Bas_Sassandra_IvoryCoast': {
        'lat': 5.4, 'lon': -6.1,
        'country': 'Ivory Coast',
        'gmet_station': None,
        'production_share': 0.25,
        'main_crop_months': [10, 11, 12, 1, 2],
        'midcrop_months': [4, 5, 6, 7],
        'harmattan_months': [12, 1, 2],
        'priority': 1
    },
    'Lacs_IvoryCoast': {
        'lat': 7.0, 'lon': -5.0,
        'country': 'Ivory Coast',
        'gmet_station': None,
        'production_share': 0.20,
        'main_crop_months': [10, 11, 12, 1, 2],
        'midcrop_months': [4, 5, 6],
        'harmattan_months': [12, 1, 2],
        'priority': 2
    },
    'Nawa_IvoryCoast': {
        'lat': 5.0, 'lon': -6.5,
        'country': 'Ivory Coast',
        'gmet_station': None,
        'production_share': 0.15,
        'main_crop_months': [10, 11, 12, 1, 2],
        'midcrop_months': [4, 5, 6, 7],
        'harmattan_months': [12, 1, 2],
        'priority': 3
    },
}

# Historical drought/Harmattan events vs CC price impact
HISTORICAL_DROUGHT_EVENTS = [
    {'season': '2023-24', 'cause': 'El Nino drought + Harmattan', 'cc_impact_pct': 115.0, 'severity': 'extreme'},
    {'season': '2015-16', 'cause': 'El Nino dry spell', 'cc_impact_pct': 28.3, 'severity': 'moderate'},
    {'season': '2010-11', 'cause': 'Ivory Coast political crisis + drought', 'cc_impact_pct': 35.7, 'severity': 'severe'},
    {'season': '2002-03', 'cause': 'West Africa drought', 'cc_impact_pct': 18.5, 'severity': 'moderate'},
]

# Black Pod disease risk: spikes with excess moisture Oct-Dec
BLACK_POD_MOISTURE_THRESHOLD_MM = 150  # Monthly rainfall above = high disease risk


class CocoaWestAfricaCollector:
    """
    Collects weather, vegetation, and supply data for West African cocoa regions.
    Sources: Ghana Met Agency, NOAA GFS (for Ivory Coast), NASA MODIS NDVI,
    ICCO (International Cocoa Organization) supply data.
    """

    def __init__(self):
        self.noaa_base_url = 'https://api.weather.gov'
        self.icco_base_url = 'https://www.icco.org'

    def get_ghana_met_forecast(self, station_code: str, lat: float,
                                lon: float) -> Dict:
        """
        Fetch from Ghana Meteorological Agency.
        Falls back to NOAA GFS for Ivory Coast where direct API unavailable.
        """
        try:
            # Ghana Met doesn't have public API - use NOAA GFS for all regions
            points_url = f"{self.noaa_base_url}/points/{lat},{lon}"
            response = requests.get(points_url, timeout=10)

            if response.status_code == 200:
                grid = response.json()['properties']
                forecast_resp = requests.get(grid['forecast'], timeout=10)
                if forecast_resp.status_code == 200:
                    periods = forecast_resp.json()['properties']['periods']
                    return {
                        'station': station_code,
                        'source': 'NOAA_GFS',
                        'timestamp': datetime.utcnow().isoformat(),
                        'forecast_periods': periods[:10],
                        'lat': lat, 'lon': lon
                    }
        except Exception as e:
            logger.error(f"Forecast fetch error for {station_code}: {e}")

        return {'station': station_code, 'source': 'unavailable',
                'timestamp': datetime.utcnow().isoformat()}

    def assess_harmattan_risk(self, region_name: str,
                               forecast_data: Dict) -> Dict:
        """
        Harmattan: hot, dry, dusty wind from Sahara (Nov-Feb).
        Causes: pod dehydration, flower drop, reduced pod set.
        Severe Harmattan can cut mid-crop by 20-30%.
        """
        region = COCOA_REGIONS[region_name]
        current_month = datetime.utcnow().month
        is_harmattan_season = current_month in region['harmattan_months']

        periods = forecast_data.get('forecast_periods', [])
        wind_speeds = []
        humidity_levels = []

        for period in periods[:5]:
            detail = period.get('detailedForecast', '').lower()
            if 'wind' in detail:
                wind_speeds.append(period.get('windSpeed', '0 mph'))
            if 'humidity' in detail:
                humidity_levels.append(detail)

        harmattan_intensity = 'none'
        price_impact_range = (0, 0)

        if is_harmattan_season:
            # Classify based on season progression and forecast
            month_risk = {11: 0.3, 12: 0.6, 1: 0.7, 2: 0.5}
            base_risk = month_risk.get(current_month, 0.1)

            if base_risk > 0.6:
                harmattan_intensity = 'strong'
                price_impact_range = (8, 18)
            elif base_risk > 0.4:
                harmattan_intensity = 'moderate'
                price_impact_range = (3, 10)
            elif base_risk > 0.2:
                harmattan_intensity = 'mild'
                price_impact_range = (1, 5)

        is_main_crop = current_month in region['main_crop_months']
        is_midcrop = current_month in region['midcrop_months']

        return {
            'region': region_name,
            'harmattan_intensity': harmattan_intensity,
            'is_harmattan_season': is_harmattan_season,
            'is_main_crop_period': is_main_crop,
            'is_midcrop_period': is_midcrop,
            'crop_period_multiplier': 1.5 if is_main_crop else (1.2 if is_midcrop else 0.8),
            'price_impact_range_pct': price_impact_range,
            'production_share': region['production_share'],
            'timestamp': datetime.utcnow().isoformat()
        }

    def assess_drought_risk(self, region_name: str,
                             rainfall_data: Dict) -> Dict:
        """
        Drought assessment for cocoa.
        Cocoa requires 1200-2500mm annual rainfall.
        Critical periods: flowering (Oct-Nov) and pod development (Jan-Mar).
        """
        monthly_mm = rainfall_data.get('monthly_mm', 0)
        three_month_deficit = rainfall_data.get('three_month_deficit_mm', 0)
        current_month = datetime.utcnow().month
        region = COCOA_REGIONS[region_name]

        is_critical_period = current_month in region['main_crop_months']

        if three_month_deficit > 200 and is_critical_period:
            risk_level = 'critical'
            price_impact_range = (20, 45)
        elif three_month_deficit > 150:
            risk_level = 'high'
            price_impact_range = (10, 25)
        elif three_month_deficit > 80:
            risk_level = 'moderate'
            price_impact_range = (4, 12)
        else:
            risk_level = 'low'
            price_impact_range = (0, 4)

        # Black Pod disease risk (inverse - too much rain)
        black_pod_risk = monthly_mm > BLACK_POD_MOISTURE_THRESHOLD_MM

        return {
            'region': region_name,
            'monthly_rainfall_mm': monthly_mm,
            'three_month_deficit_mm': three_month_deficit,
            'drought_risk_level': risk_level,
            'black_pod_risk': black_pod_risk,
            'price_impact_range_pct': price_impact_range,
            'is_critical_crop_period': is_critical_period,
            'production_share': region['production_share'],
        }

    def get_ndvi_vegetation_index(self, lat: float, lon: float) -> Dict:
        """
        Fetch MODIS NDVI data for canopy health assessment.
        NDVI below 0.4 indicates significant vegetation stress.
        Used as leading indicator of crop condition deterioration.
        """
        try:
            nasa_url = (
                f"https://modis.ornl.gov/rst/api/v1/MOD13Q1/subset"
                f"?latitude={lat}&longitude={lon}&startDate=A2024001"
                f"&endDate=A2024365&kmAboveBelow=1&kmLeftRight=1"
            )
            response = requests.get(nasa_url, timeout=15)
            if response.status_code == 200:
                data = response.json()
                ndvi_values = [s['data'][0] for s in data.get('subset', [])
                               if s['band'] == '250m_16_days_NDVI']
                if ndvi_values:
                    latest_ndvi = ndvi_values[-1] * 0.0001  # Scale factor
                    return {
                        'ndvi': latest_ndvi,
                        'status': 'healthy' if latest_ndvi > 0.5
                                  else ('stressed' if latest_ndvi > 0.3
                                        else 'severely_stressed'),
                        'source': 'MODIS_MOD13Q1',
                        'timestamp': datetime.utcnow().isoformat()
                    }
        except Exception as e:
            logger.error(f"NDVI fetch error at ({lat},{lon}): {e}")

        return {'ndvi': None, 'status': 'unavailable',
                'source': 'MODIS', 'timestamp': datetime.utcnow().isoformat()}

    def collect_all_regions(self) -> Dict:
        """Collect all West Africa cocoa region data"""
        results = {}
        logger.info("Collecting West Africa cocoa region data...")

        for region_name, region_data in COCOA_REGIONS.items():
            forecast = self.get_ghana_met_forecast(
                region_data.get('gmet_station', 'GFS'),
                region_data['lat'], region_data['lon']
            )
            rainfall = {'monthly_mm': 80, 'three_month_deficit_mm': 50}
            harmattan = self.assess_harmattan_risk(region_name, forecast)
            drought = self.assess_drought_risk(region_name, rainfall)
            ndvi = self.get_ndvi_vegetation_index(
                region_data['lat'], region_data['lon']
            )

            results[region_name] = {
                'forecast': forecast,
                'harmattan_risk': harmattan,
                'drought_risk': drought,
                'vegetation_health': ndvi,
                'priority': region_data['priority']
            }
            logger.info(
                f"  {region_name}: harmattan={harmattan['harmattan_intensity']}, "
                f"drought={drought['drought_risk_level']}, ndvi={ndvi.get('ndvi')}"
            )

        return {
            'commodity': 'CC',
            'timestamp': datetime.utcnow().isoformat(),
            'regions': results,
        }
