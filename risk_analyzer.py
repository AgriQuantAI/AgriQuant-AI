"""
AgriQuant AI Risk Analysis Module
Comprehensive supply risk assessment for agricultural commodities
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Supply risk levels"""
    CRITICAL = "CRITICAL"  # >20% crop loss expected
    HIGH = "HIGH"          # 10-20% crop loss
    MODERATE = "MODERATE"  # 5-10% crop loss
    LOW = "LOW"            # 2-5% crop loss
    MINIMAL = "MINIMAL"    # <2% crop loss


class EventType(Enum):
    """Weather event types"""
    FREEZE = "FREEZE"
    HURRICANE = "HURRICANE"
    DROUGHT = "DROUGHT"
    DISEASE = "DISEASE"
    FLOOD = "FLOOD"


@dataclass
class RiskAssessment:
    """Supply risk assessment output"""
    timestamp: datetime
    event_type: EventType
    risk_level: RiskLevel
    probability: float  # 0-1
    expected_crop_damage_pct: float
    affected_counties: List[str]
    total_production_affected_pct: float
    confidence: float
    timeline: str
    factors: Dict[str, float]
    recommendation: str


class GroveHealthMonitor:
    """
    Monitor current grove health conditions
    Affects vulnerability to weather events
    """
    
    def __init__(self):
        self.drought_stress_level = 0.0  # 0-1 scale
        self.disease_pressure = 0.0  # 0-1 scale
        self.tree_age_distribution = {}
        self.canopy_health_index = 1.0  # 0-1 scale
        
    def calculate_vulnerability_multiplier(
        self,
        event_type: EventType
    ) -> float:
        """
        Calculate how current grove health affects vulnerability
        
        Returns multiplier (1.0 = normal, >1.0 = more vulnerable)
        """
        base_vulnerability = 1.0
        
        if event_type == EventType.FREEZE:
            # Drought-stressed trees more vulnerable to freeze
            freeze_multiplier = 1.0 + (self.drought_stress_level * 0.3)
            # Diseased trees also more vulnerable
            freeze_multiplier *= (1.0 + (self.disease_pressure * 0.2))
            return freeze_multiplier
            
        elif event_type == EventType.DISEASE:
            # Already high disease pressure makes it worse
            disease_multiplier = 1.0 + (self.disease_pressure * 0.5)
            # Stressed trees more susceptible
            disease_multiplier *= (1.0 + (self.drought_stress_level * 0.2))
            return disease_multiplier
            
        elif event_type == EventType.DROUGHT:
            # Already stressed trees compound the problem
            drought_multiplier = 1.0 + (self.drought_stress_level * 0.4)
            return drought_multiplier
            
        else:
            return base_vulnerability
    
    def update_from_satellite_data(
        self,
        ndvi_data: pd.DataFrame,
        soil_moisture: float
    ):
        """Update grove health from satellite imagery"""
        # NDVI (Normalized Difference Vegetation Index)
        # Healthy vegetation: 0.6-0.9
        # Stressed vegetation: 0.2-0.5
        # Bare soil/dead: <0.2
        
        avg_ndvi = ndvi_data['ndvi'].mean()
        
        if avg_ndvi > 0.7:
            self.canopy_health_index = 1.0
        elif avg_ndvi > 0.5:
            self.canopy_health_index = 0.7
        elif avg_ndvi > 0.3:
            self.canopy_health_index = 0.4
        else:
            self.canopy_health_index = 0.2
        
        # Soil moisture affects drought stress
        if soil_moisture < 0.3:
            self.drought_stress_level = 0.8
        elif soil_moisture < 0.5:
            self.drought_stress_level = 0.5
        else:
            self.drought_stress_level = 0.2
        
        logger.info(f"Grove health updated: NDVI={avg_ndvi:.2f}, "
                   f"Health={self.canopy_health_index:.2f}")


class SupplyRiskAnalyzer:
    """
    Comprehensive supply risk analysis for agricultural crop
    
    Combines:
    - Weather forecasts
    - Historical patterns
    - Current grove health
    - Geographic concentration
    - Academic research models
    """
    
    def __init__(self):
        self.grove_monitor = GroveHealthMonitor()
        self.historical_events = self._load_historical_database()
        
        # Florida county production percentages
        self.county_production = {
            'Polk': 0.35,      # 35% of FL production
            'Highlands': 0.20,
            'Hardee': 0.10,
            'DeSoto': 0.05,
            'St. Lucie': 0.08,
            'Indian River': 0.07,
            'Others': 0.15
        }
    
    def assess_freeze_risk(
        self,
        forecast_temp: float,
        duration_hours: float,
        affected_counties: List[str],
        wind_speed: float,
        forecast_confidence: float
    ) -> RiskAssessment:
        """
        Assess crop damage risk from freeze event
        
        Based on:
        - Temperature thresholds (28°F = critical, 26°F = severe)
        - Duration of freeze
        - Wind conditions (low wind = worse)
        - Current grove health
        - Geographic scope
        """
        
        # Temperature damage curve
        if forecast_temp >= 28:
            base_damage = 0.02  # 2% - minimal damage
        elif forecast_temp >= 26:
            base_damage = 0.08  # 8% - moderate damage
        elif forecast_temp >= 24:
            base_damage = 0.15  # 15% - significant damage
        else:
            base_damage = 0.25  # 25%+ - severe damage
        
        # Duration factor
        if duration_hours < 2:
            duration_factor = 0.5
        elif duration_hours < 4:
            duration_factor = 1.0
        elif duration_hours < 6:
            duration_factor = 1.3
        else:
            duration_factor = 1.6
        
        # Wind factor (low wind = worse for citrus)
        if wind_speed < 5:
            wind_factor = 1.3  # Still air = enhanced cooling
        elif wind_speed < 10:
            wind_factor = 1.1
        else:
            wind_factor = 0.9  # Wind mixes warmer air
        
        # Grove health vulnerability
        health_multiplier = self.grove_monitor.calculate_vulnerability_multiplier(
            EventType.FREEZE
        )
        
        # Calculate expected damage
        expected_damage = (base_damage * duration_factor * 
                          wind_factor * health_multiplier)
        expected_damage = min(expected_damage, 0.50)  # Cap at 50%
        
        # Geographic scope
        affected_production_pct = sum(
            self.county_production.get(county, 0) 
            for county in affected_counties
        )
        
        # Overall supply impact
        total_impact = expected_damage * affected_production_pct
        
        # Risk level classification
        if total_impact > 0.15:
            risk_level = RiskLevel.CRITICAL
        elif total_impact > 0.08:
            risk_level = RiskLevel.HIGH
        elif total_impact > 0.04:
            risk_level = RiskLevel.MODERATE
        elif total_impact > 0.02:
            risk_level = RiskLevel.LOW
        else:
            risk_level = RiskLevel.MINIMAL
        
        # Find similar historical events
        similar_events = self._find_similar_freeze_events(
            forecast_temp, duration_hours
        )
        
        # Recommendation
        if risk_level in [RiskLevel.CRITICAL, RiskLevel.HIGH]:
            recommendation = f"ALERT: Significant supply disruption expected. " \
                           f"Historical precedent: {len(similar_events)} similar events " \
                           f"averaged {np.mean([e['damage_pct'] for e in similar_events]):.1%} crop loss."
        else:
            recommendation = f"Monitor: {total_impact:.1%} supply impact expected. " \
                           f"Within normal seasonal variation."
        
        return RiskAssessment(
            timestamp=datetime.now(),
            event_type=EventType.FREEZE,
            risk_level=risk_level,
            probability=forecast_confidence,
            expected_crop_damage_pct=expected_damage,
            affected_counties=affected_counties,
            total_production_affected_pct=total_impact,
            confidence=forecast_confidence,
            timeline=f"Freeze in {duration_hours} hours, {duration_hours}h duration",
            factors={
                'temperature': forecast_temp,
                'duration_hours': duration_hours,
                'wind_speed': wind_speed,
                'grove_health': health_multiplier,
                'affected_production': affected_production_pct
            },
            recommendation=recommendation
        )
    
    def assess_hurricane_risk(
        self,
        forecast_path: List[Tuple[float, float]],  # lat/lon coordinates
        wind_speed: int,
        rainfall_inches: float,
        confidence: float
    ) -> RiskAssessment:
        """
        Assess crop damage from hurricane
        
        Factors:
        - Wind damage (fruit drop, tree damage)
        - Flooding risk
        - Disease pressure (post-storm)
        - Path through agricultural production zones
        """
        
        # Check if path intersects agricultural production zones
        # Florida agricultural production zones: roughly 27-28°N, 80-82°W
        citrus_belt = {
            'lat_min': 27.0,
            'lat_max': 28.5,
            'lon_min': -82.0,
            'lon_max': -80.5
        }
        
        path_intersects = any(
            citrus_belt['lat_min'] <= lat <= citrus_belt['lat_max'] and
            citrus_belt['lon_min'] <= lon <= citrus_belt['lon_max']
            for lat, lon in forecast_path
        )
        
        if not path_intersects:
            # Path misses agricultural production zones
            return RiskAssessment(
                timestamp=datetime.now(),
                event_type=EventType.HURRICANE,
                risk_level=RiskLevel.MINIMAL,
                probability=confidence,
                expected_crop_damage_pct=0.01,
                affected_counties=[],
                total_production_affected_pct=0.01,
                confidence=confidence,
                timeline="Hurricane path diverges from agricultural production zones",
                factors={
                    'wind_speed': wind_speed,
                    'rainfall': rainfall_inches,
                    'path_intersects': False
                },
                recommendation="No significant supply impact expected"
            )
        
        # Path hits agricultural production zones - assess damage
        
        # Wind damage (fruit drop mainly)
        if wind_speed < 60:
            wind_damage = 0.05  # 5% fruit drop
        elif wind_speed < 80:
            wind_damage = 0.12  # 12% fruit drop
        elif wind_speed < 100:
            wind_damage = 0.20  # 20% fruit drop + some tree damage
        else:
            wind_damage = 0.30  # Severe damage
        
        # Flooding/disease risk from rainfall
        if rainfall_inches > 10:
            flood_disease_factor = 1.3
        elif rainfall_inches > 6:
            flood_disease_factor = 1.15
        else:
            flood_disease_factor = 1.0
        
        expected_damage = wind_damage * flood_disease_factor
        
        # Assume hurricane affects 60-80% of agricultural production zones if direct hit
        affected_production = 0.70
        total_impact = expected_damage * affected_production
        
        # Risk level
        if total_impact > 0.15:
            risk_level = RiskLevel.CRITICAL
        elif total_impact > 0.08:
            risk_level = RiskLevel.HIGH
        else:
            risk_level = RiskLevel.MODERATE
        
        affected_counties = ['Polk', 'Highlands', 'Hardee', 'DeSoto']
        
        return RiskAssessment(
            timestamp=datetime.now(),
            event_type=EventType.HURRICANE,
            risk_level=risk_level,
            probability=confidence,
            expected_crop_damage_pct=expected_damage,
            affected_counties=affected_counties,
            total_production_affected_pct=total_impact,
            confidence=confidence,
            timeline=f"Hurricane landfall expected, {wind_speed}mph winds",
            factors={
                'wind_speed': wind_speed,
                'rainfall': rainfall_inches,
                'flood_factor': flood_disease_factor
            },
            recommendation=f"ALERT: Direct hit on agricultural production zones. "
                         f"{total_impact:.1%} supply impact expected."
        )
    
    def assess_disease_risk(
        self,
        temp_avg: float,
        humidity_avg: float,
        rainfall_days: int,
        current_disease_pressure: float
    ) -> RiskAssessment:
        """
        Assess crop disease disease risk
        
        Asian citrus psyllid (disease vector) thrives in:
        - Warm temps (75-85°F)
        - High humidity (>70%)
        - Wet conditions
        """
        
        # Temperature favorability
        if 75 <= temp_avg <= 85:
            temp_score = 1.0  # Optimal
        elif 70 <= temp_avg <= 90:
            temp_score = 0.7  # Favorable
        else:
            temp_score = 0.3  # Less favorable
        
        # Humidity favorability
        if humidity_avg > 80:
            humidity_score = 1.0
        elif humidity_avg > 70:
            humidity_score = 0.8
        else:
            humidity_score = 0.4
        
        # Rainfall favorability
        if rainfall_days > 15:
            rain_score = 1.0
        elif rainfall_days > 10:
            rain_score = 0.7
        else:
            rain_score = 0.4
        
        # Combined disease favorability
        disease_favorability = (temp_score + humidity_score + rain_score) / 3
        
        # Expected population increase
        # Li et al. (2020): Favorable conditions → 18-24% psyllid increase
        population_increase = disease_favorability * 0.22
        
        # Crop damage estimate (simplified)
        # Higher disease pressure → more transmission → more yield loss
        expected_damage = population_increase * 0.3  # 30% of population increase
        
        # Adjust for current disease pressure
        if current_disease_pressure > 0.5:
            expected_damage *= 1.5  # Already high pressure makes it worse
        
        expected_damage = min(expected_damage, 0.15)  # Cap at 15%
        
        # This affects entire state
        total_impact = expected_damage
        
        if total_impact > 0.08:
            risk_level = RiskLevel.HIGH
        elif total_impact > 0.05:
            risk_level = RiskLevel.MODERATE
        else:
            risk_level = RiskLevel.LOW
        
        return RiskAssessment(
            timestamp=datetime.now(),
            event_type=EventType.DISEASE,
            risk_level=risk_level,
            probability=0.75,  # Disease pressure is more certain
            expected_crop_damage_pct=expected_damage,
            affected_counties=list(self.county_production.keys()),
            total_production_affected_pct=total_impact,
            confidence=0.75,
            timeline="Impact over 3-6 month period",
            factors={
                'temp_favorability': temp_score,
                'humidity_favorability': humidity_score,
                'rainfall_favorability': rain_score,
                'current_pressure': current_disease_pressure
            },
            recommendation=f"Monitor: {total_impact:.1%} yield reduction expected from "
                         f"increased disease pressure. Impact accumulates over months."
        )
    
    def _find_similar_freeze_events(
        self,
        temp: float,
        duration: float
    ) -> List[Dict]:
        """Find historical freeze events with similar conditions"""
        similar = []
        
        for event in self.historical_events.get(EventType.FREEZE, []):
            temp_diff = abs(event['temp'] - temp)
            duration_diff = abs(event['duration'] - duration)
            
            if temp_diff < 3 and duration_diff < 2:
                similar.append(event)
        
        return similar
    
    def _load_historical_database(self) -> Dict[EventType, List[Dict]]:
        """Load historical weather events database"""
        # Simplified - in production, load from database
        return {
            EventType.FREEZE: [
                {'date': '2024-01-16', 'temp': 26, 'duration': 5, 'damage_pct': 0.14},
                {'date': '2022-01-29', 'temp': 28, 'duration': 4, 'damage_pct': 0.08},
                {'date': '2010-01-09', 'temp': 24, 'duration': 6, 'damage_pct': 0.22},
                # ... more events
            ],
            EventType.HURRICANE: [
                {'name': 'Irma', 'year': 2017, 'wind': 115, 'damage_pct': 0.18},
                {'name': 'Charley', 'year': 2004, 'wind': 145, 'damage_pct': 0.25},
                # ... more events
            ]
        }
    
    def generate_risk_report(self, assessment: RiskAssessment) -> str:
        """Generate formatted risk report"""
        report = "=" * 70 + "\n"
        report += "AGRIQUANT AI SUPPLY RISK ASSESSMENT\n"
        report += "=" * 70 + "\n\n"
        
        report += f"Timestamp: {assessment.timestamp.strftime('%Y-%m-%d %H:%M UTC')}\n"
        report += f"Event Type: {assessment.event_type.value}\n"
        report += f"Risk Level: {assessment.risk_level.value}\n"
        report += f"Probability: {assessment.probability:.0%}\n\n"
        
        report += "IMPACT ASSESSMENT\n"
        report += "-" * 70 + "\n"
        report += f"Expected Crop Damage: {assessment.expected_crop_damage_pct:.1%}\n"
        report += f"Total Supply Impact: {assessment.total_production_affected_pct:.1%}\n"
        report += f"Affected Counties: {', '.join(assessment.affected_counties)}\n"
        report += f"Confidence: {assessment.confidence:.0%}\n\n"
        
        report += "TIMELINE\n"
        report += "-" * 70 + "\n"
        report += f"{assessment.timeline}\n\n"
        
        report += "CONTRIBUTING FACTORS\n"
        report += "-" * 70 + "\n"
        for factor, value in assessment.factors.items():
            report += f"{factor}: {value}\n"
        report += "\n"
        
        report += "RECOMMENDATION\n"
        report += "-" * 70 + "\n"
        report += f"{assessment.recommendation}\n"
        report += "=" * 70 + "\n"
        
        return report


if __name__ == "__main__":
    # Example usage
    analyzer = SupplyRiskAnalyzer()
    
    # Assess freeze risk
    freeze_assessment = analyzer.assess_freeze_risk(
        forecast_temp=26.0,
        duration_hours=5.0,
        affected_counties=['Polk', 'Highlands'],
        wind_speed=3.0,
        forecast_confidence=0.85
    )
    
    print(analyzer.generate_risk_report(freeze_assessment))
