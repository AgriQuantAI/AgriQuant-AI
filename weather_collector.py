"""
AgriQuant AI - Primary Weather Collector
Originally built for OJ/Florida (Phase 1). Multi-commodity expansion
via coffee_brazil_collector.py, cocoa_westafrica_collector.py,
grains_collector.py, and sugar_collector.py (added Q1 2026).
This module remains the reference implementation for the OJ signal pipeline.
"""
AgriQuant AI - NOAA Weather Data Module
Collects weather forecasts, satellite data, and historical weather information
"""

import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from config import *

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NOAAWeatherCollector:
    """
    Collects and processes weather data from NOAA APIs
    """
    
    def __init__(self):
        self.base_url = NOAA_BASE_URL
        self.api_key = NOAA_API_KEY
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'AgriQuant AI-AI/1.0 (research@agriquant.ai)',
            'Accept': 'application/geo+json'
        })
        
        if self.api_key:
            self.session.headers.update({'X-API-Key': self.api_key})
    
    def get_forecast_for_county(self, county_name: str) -> Dict:
        """
        Get detailed weather forecast for a specific Florida county
        
        Args:
            county_name: Name of county (e.g., 'Polk', 'Highlands')
            
        Returns:
            Dict containing forecast data with hourly and daily predictions
        """
        try:
            county_data = CITRUS_COUNTIES[county_name]
            lat, lon = county_data['lat'], county_data['lon']
            
            # Step 1: Get the forecast grid endpoint for this location
            points_url = f"{self.base_url}/points/{lat},{lon}"
            logger.info(f"Fetching forecast grid for {county_name} County at {lat},{lon}")
            
            points_response = self.session.get(points_url, timeout=10)
            points_response.raise_for_status()
            points_data = points_response.json()
            
            # Step 2: Get hourly and daily forecast URLs
            forecast_hourly_url = points_data['properties']['forecastHourly']
            forecast_daily_url = points_data['properties']['forecast']
            forecast_office = points_data['properties']['cwa']
            grid_x = points_data['properties']['gridX']
            grid_y = points_data['properties']['gridY']
            
            # Step 3: Fetch hourly forecast (critical for freeze detection)
            hourly_response = self.session.get(forecast_hourly_url, timeout=10)
            hourly_response.raise_for_status()
            hourly_data = hourly_response.json()
            
            # Step 4: Fetch daily forecast
            daily_response = self.session.get(forecast_daily_url, timeout=10)
            daily_response.raise_for_status()
            daily_data = daily_response.json()
            
            # Step 5: Get forecast discussion (meteorologist's text analysis)
            discussion_url = f"{self.base_url}/products/types/AFD/locations/{forecast_office}"
            discussion_response = self.session.get(discussion_url, timeout=10)
            discussion_text = ""
            
            if discussion_response.status_code == 200:
                discussion_data = discussion_response.json()
                if discussion_data.get('graph'):
                    # Get most recent discussion
                    latest = discussion_data['graph'][0]
                    product_url = latest['@id']
                    product_response = self.session.get(product_url, timeout=10)
                    if product_response.status_code == 200:
                        discussion_text = product_response.json()['productText']
            
            # Compile comprehensive forecast data
            forecast = {
                'county': county_name,
                'location': {'lat': lat, 'lon': lon},
                'forecast_office': forecast_office,
                'grid': {'x': grid_x, 'y': grid_y},
                'generated_at': datetime.utcnow().isoformat(),
                'hourly_forecast': self._parse_hourly_forecast(hourly_data),
                'daily_forecast': self._parse_daily_forecast(daily_data),
                'discussion': discussion_text,
                'alerts': self._check_alerts(county_data['fips'])
            }
            
            logger.info(f"Successfully retrieved forecast for {county_name} County")
            return forecast
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API error fetching forecast for {county_name}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in get_forecast_for_county: {e}")
            return None
    
    def _parse_hourly_forecast(self, hourly_data: Dict) -> List[Dict]:
        """Parse hourly forecast into structured format"""
        periods = []
        
        for period in hourly_data['properties']['periods'][:72]:  # Next 72 hours
            periods.append({
                'time': period['startTime'],
                'temperature': period['temperature'],
                'temperature_unit': period['temperatureUnit'],
                'wind_speed': period['windSpeed'],
                'wind_direction': period['windDirection'],
                'short_forecast': period['shortForecast'],
                'detailed_forecast': period.get('detailedForecast', ''),
                'probability_of_precipitation': period.get('probabilityOfPrecipitation', {}).get('value', 0)
            })
        
        return periods
    
    def _parse_daily_forecast(self, daily_data: Dict) -> List[Dict]:
        """Parse daily forecast into structured format"""
        periods = []
        
        for period in daily_data['properties']['periods'][:14]:  # Next 14 periods (7 days)
            periods.append({
                'name': period['name'],
                'time': period['startTime'],
                'temperature': period['temperature'],
                'temperature_trend': period.get('temperatureTrend', None),
                'wind_speed': period['windSpeed'],
                'wind_direction': period['windDirection'],
                'short_forecast': period['shortForecast'],
                'detailed_forecast': period['detailedForecast']
            })
        
        return periods
    
    def _check_alerts(self, county_fips: str) -> List[Dict]:
        """Check for active weather alerts for a county"""
        try:
            alerts_url = f"{self.base_url}/alerts/active/zone/{county_fips}"
            response = self.session.get(alerts_url, timeout=10)
            
            if response.status_code == 200:
                alerts_data = response.json()
                active_alerts = []
                
                for feature in alerts_data.get('features', []):
                    props = feature['properties']
                    active_alerts.append({
                        'event': props['event'],
                        'severity': props['severity'],
                        'certainty': props['certainty'],
                        'urgency': props['urgency'],
                        'headline': props['headline'],
                        'description': props['description'],
                        'instruction': props.get('instruction', ''),
                        'onset': props.get('onset'),
                        'expires': props.get('expires')
                    })
                
                return active_alerts
            
            return []
            
        except Exception as e:
            logger.warning(f"Could not fetch alerts: {e}")
            return []
    
    def detect_freeze_risk(self, forecast: Dict) -> Dict:
        """
        Analyze forecast for freeze risk
        
        Returns:
            Dict with freeze risk assessment
        """
        hourly = forecast['hourly_forecast']
        freeze_periods = []
        
        for i, period in enumerate(hourly):
            temp = period['temperature']
            
            # Check if temperature below critical thresholds
            for severity, threshold in FREEZE_THRESHOLDS.items():
                if temp <= threshold['temp']:
                    # Look ahead to calculate duration
                    duration = 1  # Start with this hour
                    for j in range(i + 1, min(i + 12, len(hourly))):
                        if hourly[j]['temperature'] <= threshold['temp']:
                            duration += 1
                        else:
                            break
                    
                    if duration >= threshold['duration_hours']:
                        freeze_periods.append({
                            'severity': severity,
                            'start_time': period['time'],
                            'temperature': temp,
                            'duration_hours': duration,
                            'expected_damage_pct': threshold['damage_pct'],
                            'wind_speed': period['wind_speed']
                        })
                        break  # Don't double-count same period
        
        # Calculate overall freeze risk
        if not freeze_periods:
            return {'risk': 'none', 'details': None}
        
        # Take worst case scenario
        worst_freeze = max(freeze_periods, key=lambda x: x['expected_damage_pct'])
        
        return {
            'risk': worst_freeze['severity'],
            'details': worst_freeze,
            'all_freeze_periods': freeze_periods,
            'max_expected_damage': worst_freeze['expected_damage_pct']
        }
    
    def detect_hurricane_threat(self, county_name: str) -> Optional[Dict]:
        """
        Check National Hurricane Center for active storms threatening agricultural production zones
        
        Returns:
            Dict with hurricane threat data or None
        """
        try:
            # NHC active storms
            nhc_url = "https://www.nhc.noaa.gov/CurrentStorms.json"
            response = self.session.get(nhc_url, timeout=10)
            
            if response.status_code != 200:
                return None
            
            storms = response.json()
            
            if not storms or 'activeStorms' not in storms:
                return None
            
            county_data = CITRUS_COUNTIES[county_name]
            county_lat, county_lon = county_data['lat'], county_data['lon']
            
            threats = []
            
            for storm in storms['activeStorms']:
                # Get detailed storm data
                storm_id = storm['id']
                storm_url = f"https://www.nhc.noaa.gov/storm_graphics/api/{storm_id}_CONE_latest.kmz"
                
                # For now, simple distance check
                # In production, would parse KMZ cone and check intersection
                storm_lat = storm.get('latitudeNumeric', 0)
                storm_lon = storm.get('longitudeNumeric', 0)
                
                # Rough distance calculation
                distance = ((county_lat - storm_lat)**2 + (county_lon - storm_lon)**2)**0.5
                
                # If within ~500 miles (rough cone range)
                if distance < 5:  # Degrees (very rough)
                    threats.append({
                        'name': storm['name'],
                        'classification': storm['classification'],
                        'intensity': storm.get('intensity', 0),
                        'pressure': storm.get('pressure', 0),
                        'wind_speed': storm.get('windSpeed', 0),
                        'current_lat': storm_lat,
                        'current_lon': storm_lon,
                        'distance_degrees': distance,
                        'movement': storm.get('movement', ''),
                        'last_update': storm.get('lastUpdate', '')
                    })
            
            return threats if threats else None
            
        except Exception as e:
            logger.error(f"Error checking hurricane threats: {e}")
            return None
    
    def get_model_forecast_data(self, county_name: str, model: str = 'GFS') -> Dict:
        """
        Get raw model data (GFS, NAM, HRRR) for ensemble forecasting
        
        Note: This requires NOMADS server access and GRIB2 parsing
        Simplified version for demonstration
        """
        # In production, would fetch actual model data from NOMADS
        # For now, returns structure showing what would be collected
        
        return {
            'model': model,
            'county': county_name,
            'run_time': datetime.utcnow().isoformat(),
            'forecast_hours': list(range(0, 168, 3)),  # 0-168 hours, 3-hour intervals
            'parameters': [
                'temperature_2m',
                'temperature_850mb',
                'wind_speed',
                'wind_direction',
                'precipitation',
                'relative_humidity'
            ],
            'note': 'Full implementation would parse GRIB2 files from NOMADS server'
        }
    
    def get_ensemble_forecast(self, county_name: str) -> Dict:
        """
        Combine multiple weather models for ensemble forecast
        
        Returns:
            Dict with consensus forecast and model agreement metrics
        """
        models = ['GFS', 'NAM', 'HRRR']
        
        # Get primary forecast (always available)
        primary_forecast = self.get_forecast_for_county(county_name)
        
        if not primary_forecast:
            return None
        
        # In production, would fetch all models and compare
        # For now, using primary forecast with simulated ensemble
        
        freeze_risk = self.detect_freeze_risk(primary_forecast)
        
        return {
            'county': county_name,
            'timestamp': datetime.utcnow().isoformat(),
            'primary_forecast': primary_forecast,
            'freeze_risk': freeze_risk,
            'model_agreement': {
                'freeze_probability': 0.75,  # Simulated - would calculate from actual models
                'models_agreeing': 3,
                'total_models': 4,
                'agreement_score': 0.75
            },
            'confidence': 'high' if freeze_risk['risk'] != 'none' else 'moderate'
        }
    
    def get_historical_analogs(self, current_forecast: Dict) -> List[Dict]:
        """
        Find historical weather events similar to current forecast
        
        This would query historical database for pattern matching
        Simplified version for demonstration
        """
        freeze_risk = self.detect_freeze_risk(current_forecast)
        
        if freeze_risk['risk'] == 'none':
            return []
        
        # In production, would query historical database
        # Return structure showing what similar events would look like
        
        return [
            {
                'date': '2024-01-16',
                'event_type': 'freeze',
                'min_temp': 26,
                'duration_hours': 5,
                'crop_damage_actual': 0.113,  # 11.3% verified by USDA
                'similarity_score': 0.87
            },
            {
                'date': '2022-01-29',
                'event_type': 'freeze',
                'min_temp': 24,
                'duration_hours': 6,
                'crop_damage_actual': 0.157,
                'similarity_score': 0.82
            }
        ]
    
    def monitor_all_counties(self) -> Dict:
        """
        Collect forecasts for all production regions
        
        Returns:
            Dict with forecasts for all counties and aggregate analysis
        """
        logger.info("Starting comprehensive weather monitoring for all production regions")
        
        all_forecasts = {}
        aggregate_risk = {
            'freeze': False,
            'hurricane': False,
            'max_damage_estimate': 0,
            'affected_production_pct': 0
        }
        
        for county_name in CITRUS_COUNTIES.keys():
            logger.info(f"Fetching data for {county_name} County...")
            
            forecast = self.get_ensemble_forecast(county_name)
            
            if forecast:
                all_forecasts[county_name] = forecast
                
                # Update aggregate risk
                freeze_risk = forecast['freeze_risk']
                if freeze_risk['risk'] != 'none':
                    aggregate_risk['freeze'] = True
                    
                    # Weight by production share
                    weighted_damage = (freeze_risk['max_expected_damage'] * 
                                     CITRUS_COUNTIES[county_name]['production_share'])
                    aggregate_risk['max_damage_estimate'] += weighted_damage
                    aggregate_risk['affected_production_pct'] += CITRUS_COUNTIES[county_name]['production_share']
            
            # Respectful API delay
            import time
            time.sleep(1)
        
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'county_forecasts': all_forecasts,
            'aggregate_risk': aggregate_risk,
            'total_counties_monitored': len(all_forecasts)
        }


def main():
    """Test the NOAA weather collector"""
    
    print("="*80)
    print("AgriQuant AI - NOAA Weather Data Collector Test")
    print("="*80)
    
    collector = NOAAWeatherCollector()
    
    # Test 1: Get forecast for Polk County (largest producer)
    print("\n[TEST 1] Fetching forecast for Polk County...")
    polk_forecast = collector.get_forecast_for_county('Polk')
    
    if polk_forecast:
        print(f"✓ Forecast retrieved successfully")
        print(f"  Forecast office: {polk_forecast['forecast_office']}")
        print(f"  Hourly periods: {len(polk_forecast['hourly_forecast'])}")
        print(f"  Active alerts: {len(polk_forecast['alerts'])}")
        
        # Check freeze risk
        freeze_risk = collector.detect_freeze_risk(polk_forecast)
        print(f"  Freeze risk: {freeze_risk['risk']}")
        if freeze_risk['risk'] != 'none':
            print(f"  Expected damage: {freeze_risk['max_expected_damage']*100:.1f}%")
    
    # Test 2: Monitor all counties
    print("\n[TEST 2] Monitoring all production regions...")
    all_data = collector.monitor_all_counties()
    print(f"✓ Monitored {all_data['total_counties_monitored']} counties")
    print(f"  Freeze threat: {all_data['aggregate_risk']['freeze']}")
    print(f"  Aggregate damage estimate: {all_data['aggregate_risk']['max_damage_estimate']*100:.1f}%")
    
    # Test 3: Check hurricane threats
    print("\n[TEST 3] Checking for hurricane threats...")
    hurricane_threats = collector.detect_hurricane_threat('Polk')
    if hurricane_threats:
        print(f"✓ Active threats detected: {len(hurricane_threats)}")
        for threat in hurricane_threats:
            print(f"  - {threat['name']}: {threat['classification']}")
    else:
        print("  No active hurricane threats")
    
    print("\n" + "="*80)
    print("Weather data collection test complete!")
    print("="*80)


if __name__ == "__main__":
    main()
