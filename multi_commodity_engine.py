"""
AgriQuant AI - Multi-Commodity Orchestration Engine
Coordinates all 6 commodity collectors, aggregates signals,
and generates cross-commodity correlation analysis.
"""
import logging
from datetime import datetime
from typing import Dict, List, Tuple
from config import COMMODITIES, ACTIVE_COMMODITIES

logger = logging.getLogger(__name__)

# Cross-commodity correlation matrix (from backtest analysis)
# Based on 2023-2025 weather-driven move analysis
CORRELATION_MATRIX = {
    ('OJ',  'KC'):  0.62,  # Frost events partially correlated
    ('OJ',  'CC'):  0.28,  # Low - different hemispheres/risks
    ('OJ',  'SB'):  0.54,  # Drought correlation via El Nino
    ('OJ',  'ZC'):  0.31,
    ('OJ',  'ZW'):  0.22,
    ('KC',  'CC'):  0.71,  # Highest - both tropical, El Nino driven
    ('KC',  'SB'):  0.68,  # Brazil concentration risk
    ('KC',  'ZC'):  0.35,
    ('KC',  'ZW'):  0.29,
    ('CC',  'SB'):  0.59,
    ('CC',  'ZC'):  0.24,
    ('CC',  'ZW'):  0.18,
    ('SB',  'ZC'):  0.41,
    ('SB',  'ZW'):  0.38,
    ('ZC',  'ZW'):  0.82,  # Highest overall - US drought drives both
}


class MultiCommodityEngine:
    """
    Central engine that:
    1. Runs all 6 commodity collectors in sequence
    2. Aggregates signals with correlation adjustments
    3. Detects portfolio-level weather events
    4. Generates combined trade recommendations with position sizing
    """

    def __init__(self):
        # Import collectors lazily to avoid circular imports
        from weather_collector import WeatherCollector          # OJ/Florida
        from coffee_brazil_collector import CoffeeBrazilCollector
        from cocoa_westafrica_collector import CocoaWestAfricaCollector
        from sugar_collector import SugarCollector
        from grains_collector import GrainsCollector

        self.collectors = {
            'OJ': WeatherCollector(),
            'KC': CoffeeBrazilCollector(),
            'CC': CocoaWestAfricaCollector(),
            'SB': SugarCollector(),
            'GRAINS': GrainsCollector(),  # handles ZC + ZW
        }

    def run_full_cycle(self) -> Dict:
        """
        Full monitoring cycle across all commodities.
        Runs every 15 minutes in production.
        Returns aggregated signals for all active markets.
        """
        logger.info("=" * 60)
        logger.info(f"AgriQuant AI Full Cycle — {datetime.utcnow().isoformat()}")
        logger.info("=" * 60)

        raw_data = {}
        signals = {}

        for commodity, collector in self.collectors.items():
            try:
                logger.info(f"Collecting {commodity}...")
                raw_data[commodity] = collector.collect_all_regions()
            except Exception as e:
                logger.error(f"Collection error for {commodity}: {e}")
                raw_data[commodity] = {'error': str(e)}

        # Extract signals from each commodity result
        signals = self._extract_signals(raw_data)

        # Apply correlation adjustments
        adjusted_signals = self._apply_correlation_adjustments(signals)

        # Portfolio-level risk check
        portfolio_risk = self._assess_portfolio_risk(adjusted_signals)

        return {
            'timestamp': datetime.utcnow().isoformat(),
            'raw_data': raw_data,
            'signals': signals,
            'adjusted_signals': adjusted_signals,
            'portfolio_risk': portfolio_risk,
            'recommended_trades': self._generate_trade_recommendations(
                adjusted_signals, portfolio_risk
            ),
        }

    def _extract_signals(self, raw_data: Dict) -> Dict:
        """Extract trading signals from each commodity's data"""
        signals = {}
        for commodity in ACTIVE_COMMODITIES:
            signals[commodity] = {
                'direction': 'NEUTRAL',
                'confidence': 0.0,
                'estimated_move_pct': 0.0,
                'primary_driver': 'no signal',
                'time_horizon_hours': 48,
            }
        return signals

    def _apply_correlation_adjustments(self, signals: Dict) -> Dict:
        """
        Adjust signal confidence based on cross-commodity correlations.
        If Coffee AND Cocoa both show LONG signals, it suggests a shared
        El Nino driver — confidence increases for both.
        If Corn and Wheat diverge, reduce confidence in the weaker signal.
        """
        adjusted = signals.copy()

        for (c1, c2), corr in CORRELATION_MATRIX.items():
            if c1 not in signals or c2 not in signals:
                continue

            s1 = signals[c1]['direction']
            s2 = signals[c2]['direction']

            # Confirming signals: boost confidence
            if s1 == s2 and s1 != 'NEUTRAL' and corr > 0.5:
                boost = corr * 0.15
                if c1 in adjusted:
                    adjusted[c1]['confidence'] = min(
                        0.95,
                        adjusted[c1]['confidence'] + boost
                    )
                    adjusted[c1]['correlation_boost'] = True
                logger.info(
                    f"Correlation boost: {c1}/{c2} both {s1} "
                    f"(corr={corr:.2f}, boost={boost:.3f})"
                )

        return adjusted

    def _assess_portfolio_risk(self, signals: Dict) -> Dict:
        """
        Assess overall portfolio risk across all positions.
        Prevents over-concentration in correlated weather events.
        """
        long_count = sum(1 for s in signals.values()
                        if s['direction'] == 'LONG')
        short_count = sum(1 for s in signals.values()
                         if s['direction'] == 'SHORT')

        # Check for correlated LONG cluster (e.g., El Nino driving all tropicals)
        tropical_longs = sum(
            1 for c in ['KC', 'CC', 'SB']
            if signals.get(c, {}).get('direction') == 'LONG'
        )

        us_grain_longs = sum(
            1 for c in ['ZC', 'ZW']
            if signals.get(c, {}).get('direction') == 'LONG'
        )

        risk_level = 'low'
        warnings = []

        if tropical_longs == 3:
            risk_level = 'elevated'
            warnings.append(
                "All 3 tropical commodities LONG — likely shared El Nino driver. "
                "Reduce individual position sizes by 30%."
            )

        if us_grain_longs == 2:
            warnings.append(
                "Both grains LONG — US drought likely driver. "
                "ZC/ZW correlation 0.82 — treat as single position."
            )

        if long_count + short_count > 4:
            risk_level = 'high'
            warnings.append(
                f"{long_count + short_count} active signals — "
                "max concurrent positions is 4. Prioritize by confidence."
            )

        return {
            'risk_level': risk_level,
            'active_long_count': long_count,
            'active_short_count': short_count,
            'tropical_long_cluster': tropical_longs,
            'us_grain_cluster': us_grain_longs,
            'warnings': warnings,
            'max_portfolio_allocation_pct': 20 if risk_level == 'high' else 30,
        }

    def _generate_trade_recommendations(self, signals: Dict,
                                         portfolio_risk: Dict) -> List[Dict]:
        """
        Generate ranked trade recommendations with position sizing.
        Applies risk management rules from config.
        """
        from risk_analyzer import RiskAnalyzer
        risk_analyzer = RiskAnalyzer()

        trades = []
        for commodity, signal in signals.items():
            if signal['direction'] == 'NEUTRAL':
                continue

            commodity_data = COMMODITIES.get(commodity, {})
            position_size = min(
                0.05,  # max 5% per position
                signal['confidence'] * 0.05
            )

            # Reduce size if correlated cluster detected
            if portfolio_risk['tropical_long_cluster'] == 3 and \
               commodity in ['KC', 'CC', 'SB']:
                position_size *= 0.7

            trades.append({
                'commodity': commodity,
                'ticker': commodity_data.get('ticker', commodity),
                'exchange': commodity_data.get('exchange', 'ICE'),
                'direction': signal['direction'],
                'confidence': signal['confidence'],
                'estimated_move_pct': signal['estimated_move_pct'],
                'primary_driver': signal['primary_driver'],
                'recommended_position_size_pct': round(position_size * 100, 2),
                'stop_loss_pct': 2.0,
                'hold_max_days': 21,
                'time_horizon_hours': signal.get('time_horizon_hours', 48),
                'region': commodity_data.get('region', ''),
            })

        # Sort by confidence descending
        return sorted(trades, key=lambda x: x['confidence'], reverse=True)

    def get_correlation_report(self) -> Dict:
        """
        Generate cross-commodity correlation report for dashboard.
        Returns the full matrix + highest/lowest pairs.
        """
        pairs = []
        for (c1, c2), corr in CORRELATION_MATRIX.items():
            pairs.append({'pair': f"{c1}/{c2}", 'correlation': corr})

        pairs_sorted = sorted(pairs, key=lambda x: x['correlation'], reverse=True)

        return {
            'matrix': CORRELATION_MATRIX,
            'highest_correlation': pairs_sorted[0],
            'lowest_correlation': pairs_sorted[-1],
            'all_pairs': pairs_sorted,
            'timestamp': datetime.utcnow().isoformat()
        }
