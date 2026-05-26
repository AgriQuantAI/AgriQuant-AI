"""
AgriQuant AI Market Impact Analysis
Translate weather events into price impact forecasts
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class PriceImpactForecast:
    """Price impact prediction"""
    timestamp: datetime
    current_price: float
    predicted_price: float
    expected_move_pct: float
    confidence: float
    timeline_days: int
    historical_precedents: List[Dict]
    elasticity_factor: float
    recommendation: str


class MarketImpactAnalyzer:
    """
    Translate supply disruptions into price impact forecasts
    
    Uses:
    - Supply/demand elasticity
    - Historical price responses
    - Current inventory levels
    - Market microstructure
    """
    
    def __init__(self):
        # Historical supply-price elasticity for OJ
        # Based on academic research: -0.3 to -0.5
        # (10% supply decrease → 20-33% price increase)
        self.supply_elasticity = -0.40
        
        # Current market conditions
        self.current_inventory_ratio = 1.0  # Normal = 1.0
        self.current_import_levels = 1.0    # Normal = 1.0
        
    def forecast_price_impact(
        self,
        supply_disruption_pct: float,
        current_price: float,
        event_type: str,
        timeline_days: int = 7
    ) -> PriceImpactForecast:
        """
        Forecast price impact from supply disruption
        
        Args:
            supply_disruption_pct: Expected supply reduction (0.10 = 10%)
            current_price: Current market price
            event_type: "freeze", "hurricane", "disease", etc.
            timeline_days: Days until impact fully priced in
        """
        
        # Base price impact from elasticity
        # Elasticity = % change in price / % change in quantity
        # Price change = Supply change * (1 / Elasticity)
        base_price_impact = supply_disruption_pct / abs(self.supply_elasticity)
        
        # Adjust for inventory levels
        # Low inventory → higher price sensitivity
        if self.current_inventory_ratio < 0.8:
            inventory_multiplier = 1.3
        elif self.current_inventory_ratio > 1.2:
            inventory_multiplier = 0.8
        else:
            inventory_multiplier = 1.0
        
        # Adjust for import substitution
        # High imports → lower price sensitivity
        import_multiplier = 1.0 / self.current_import_levels
        
        # Event-specific factors
        if event_type.lower() == "freeze":
            # Freeze events tend to cause panic buying
            event_multiplier = 1.2
        elif event_type.lower() == "hurricane":
            # Hurricanes more uncertain → less immediate impact
            event_multiplier = 0.9
        elif event_type.lower() == "disease":
            # Disease impacts accumulate slowly
            event_multiplier = 0.7
        else:
            event_multiplier = 1.0
        
        # Final price impact
        total_impact = (base_price_impact * inventory_multiplier * 
                       import_multiplier * event_multiplier)
        
        predicted_price = current_price * (1 + total_impact)
        
        # Find historical precedents
        precedents = self._find_historical_precedents(
            supply_disruption_pct,
            event_type
        )
        
        # Calculate confidence
        # Based on: event type certainty, historical precedent strength
        if len(precedents) >= 5:
            historical_confidence = 0.85
        elif len(precedents) >= 3:
            historical_confidence = 0.70
        else:
            historical_confidence = 0.60
        
        # Adjust confidence by timeline
        # Shorter timeline → more uncertain
        if timeline_days < 3:
            time_confidence = 0.7
        elif timeline_days < 7:
            time_confidence = 0.85
        else:
            time_confidence = 0.95
        
        overall_confidence = historical_confidence * time_confidence
        
        # Generate recommendation
        if total_impact > 0.15:
            recommendation = f"STRONG MOVE: {total_impact:.1%} expected increase. " \
                           f"Significant supply disruption with {len(precedents)} " \
                           f"historical precedents."
        elif total_impact > 0.08:
            recommendation = f"MODERATE MOVE: {total_impact:.1%} expected increase. " \
                           f"Material supply impact likely."
        else:
            recommendation = f"MINOR MOVE: {total_impact:.1%} expected increase. " \
                           f"Within normal volatility range."
        
        return PriceImpactForecast(
            timestamp=datetime.now(),
            current_price=current_price,
            predicted_price=predicted_price,
            expected_move_pct=total_impact,
            confidence=overall_confidence,
            timeline_days=timeline_days,
            historical_precedents=precedents,
            elasticity_factor=self.supply_elasticity,
            recommendation=recommendation
        )
    
    def _find_historical_precedents(
        self,
        supply_disruption: float,
        event_type: str
    ) -> List[Dict]:
        """Find similar historical events"""
        
        # Simplified historical database
        # In production, query actual database
        historical_events = {
            'freeze': [
                {'date': '2024-01', 'supply_impact': 0.13, 'price_move': 0.18},
                {'date': '2022-01', 'supply_impact': 0.08, 'price_move': 0.12},
                {'date': '2010-01', 'supply_impact': 0.20, 'price_move': 0.28},
            ],
            'hurricane': [
                {'date': '2017-09', 'supply_impact': 0.15, 'price_move': 0.10},
                {'date': '2004-08', 'supply_impact': 0.22, 'price_move': 0.19},
            ],
            'disease': [
                {'date': '2020-11', 'supply_impact': 0.06, 'price_move': 0.08},
                {'date': '2019-05', 'supply_impact': 0.07, 'price_move': 0.09},
            ]
        }
        
        events = historical_events.get(event_type.lower(), [])
        
        # Find events with similar supply impact
        similar = [
            e for e in events
            if abs(e['supply_impact'] - supply_disruption) < 0.05
        ]
        
        return similar
    
    def calculate_volatility_adjustment(
        self,
        historical_prices: pd.Series
    ) -> float:
        """
        Calculate market volatility to adjust confidence
        
        High volatility → lower confidence in predictions
        """
        returns = historical_prices.pct_change().dropna()
        volatility = returns.std() * np.sqrt(252)  # Annualized
        
        # Normal OJ volatility: ~20-30%
        # If current vol > 40%, reduce confidence
        if volatility > 0.40:
            vol_adjustment = 0.8
        elif volatility > 0.30:
            vol_adjustment = 0.9
        else:
            vol_adjustment = 1.0
        
        return vol_adjustment
    
    def estimate_timeline_to_peak(
        self,
        event_type: str,
        supply_disruption: float
    ) -> int:
        """
        Estimate days until price impact peaks
        
        Different events have different timelines:
        - Freeze: 3-7 days (quick reaction)
        - Hurricane: 5-10 days (uncertainty period)
        - Disease: 30-60 days (slow accumulation)
        """
        
        if event_type.lower() == "freeze":
            # Immediate impact, peaks quickly
            base_timeline = 5
        elif event_type.lower() == "hurricane":
            # Depends on path certainty
            base_timeline = 7
        elif event_type.lower() == "disease":
            # Gradual accumulation
            base_timeline = 45
        else:
            base_timeline = 7
        
        # Larger disruptions price in faster
        if supply_disruption > 0.15:
            timeline = int(base_timeline * 0.8)
        elif supply_disruption < 0.05:
            timeline = int(base_timeline * 1.3)
        else:
            timeline = base_timeline
        
        return timeline
    
    def generate_trading_recommendation(
        self,
        forecast: PriceImpactForecast,
        position_size_usd: float
    ) -> Dict:
        """
        Generate specific trading recommendation
        
        Returns entry, exit, stop loss levels
        """
        
        # Entry: Current price + small buffer for execution
        entry_price = forecast.current_price * 1.002  # 0.2% slippage
        
        # Target: Predicted price minus some buffer
        target_price = forecast.predicted_price * 0.95  # Take 95% of move
        
        # Stop loss: -3% from entry (risk management)
        stop_loss = entry_price * 0.97
        
        # Position sizing based on confidence
        adjusted_position = position_size_usd * forecast.confidence
        
        # Risk/reward
        potential_gain = (target_price - entry_price) / entry_price
        potential_loss = (entry_price - stop_loss) / entry_price
        risk_reward = potential_gain / potential_loss
        
        return {
            'action': 'LONG',
            'entry_price': entry_price,
            'target_price': target_price,
            'stop_loss': stop_loss,
            'position_size_usd': adjusted_position,
            'expected_gain_pct': potential_gain,
            'max_loss_pct': potential_loss,
            'risk_reward_ratio': risk_reward,
            'hold_period_days': forecast.timeline_days,
            'confidence': forecast.confidence
        }


def calculate_supply_demand_balance(
    current_production: float,
    supply_disruption: float,
    import_volume: float,
    consumption: float
) -> Dict:
    """
    Calculate overall supply/demand balance
    
    Returns market tightness indicators
    """
    
    adjusted_production = current_production * (1 - supply_disruption)
    total_supply = adjusted_production + import_volume
    
    surplus_deficit = total_supply - consumption
    balance_ratio = total_supply / consumption if consumption > 0 else 0
    
    # Market tightness
    if balance_ratio < 0.95:
        market_condition = "TIGHT"
        price_pressure = "STRONG_UPWARD"
    elif balance_ratio < 1.05:
        market_condition = "BALANCED"
        price_pressure = "NEUTRAL"
    else:
        market_condition = "OVERSUPPLIED"
        price_pressure = "DOWNWARD"
    
    return {
        'production': adjusted_production,
        'imports': import_volume,
        'total_supply': total_supply,
        'consumption': consumption,
        'balance': surplus_deficit,
        'balance_ratio': balance_ratio,
        'market_condition': market_condition,
        'price_pressure': price_pressure
    }


if __name__ == "__main__":
    # Example usage
    analyzer = MarketImpactAnalyzer()
    
    # Forecast price impact from freeze
    forecast = analyzer.forecast_price_impact(
        supply_disruption_pct=0.12,  # 12% crop loss
        current_price=380.0,  # Current ag commodity futures price
        event_type="freeze",
        timeline_days=7
    )
    
    print(f"Current Price: ${forecast.current_price:.2f}")
    print(f"Predicted Price: ${forecast.predicted_price:.2f}")
    print(f"Expected Move: {forecast.expected_move_pct:.1%}")
    print(f"Confidence: {forecast.confidence:.0%}")
    print(f"\nRecommendation: {forecast.recommendation}")
    
    # Generate trading recommendation
    trade_rec = analyzer.generate_trading_recommendation(forecast, 10000)
    print(f"\nTrading Recommendation:")
    print(f"Entry: ${trade_rec['entry_price']:.2f}")
    print(f"Target: ${trade_rec['target_price']:.2f}")
    print(f"Stop: ${trade_rec['stop_loss']:.2f}")
    print(f"R/R: {trade_rec['risk_reward_ratio']:.2f}")
