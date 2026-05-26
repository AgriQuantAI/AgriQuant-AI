"""
AgriQuant AI - Market Microstructure Analyzer
Advanced order flow and liquidity analysis for ag commodity futures
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import deque
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MarketMicrostructureAnalyzer:
    """
    Analyzes market microstructure for ag commodity futures
    - Order flow imbalance
    - Liquidity metrics
    - Price impact models
    - Volume profile analysis
    """
    
    def __init__(self, lookback_window: int = 100):
        self.lookback_window = lookback_window
        self.trade_history = deque(maxlen=lookback_window)
        self.quote_history = deque(maxlen=lookback_window)
    
    def update_trade(
        self,
        timestamp: datetime,
        price: float,
        volume: int,
        side: str  # 'buy' or 'sell'
    ):
        """Record new trade"""
        self.trade_history.append({
            'timestamp': timestamp,
            'price': price,
            'volume': volume,
            'side': side
        })
    
    def update_quote(
        self,
        timestamp: datetime,
        bid_price: float,
        bid_size: int,
        ask_price: float,
        ask_size: int
    ):
        """Record new quote"""
        self.quote_history.append({
            'timestamp': timestamp,
            'bid_price': bid_price,
            'bid_size': bid_size,
            'ask_price': ask_price,
            'ask_size': ask_size,
            'mid_price': (bid_price + ask_price) / 2,
            'spread': ask_price - bid_price,
            'spread_bps': ((ask_price - bid_price) / bid_price) * 10000
        })
    
    def calculate_order_flow_imbalance(self, window_minutes: int = 15) -> Dict:
        """
        Calculate order flow imbalance over recent period
        
        Args:
            window_minutes: Time window for calculation
            
        Returns:
            Order flow metrics
        """
        if len(self.trade_history) < 10:
            return {'error': 'Insufficient trade data'}
        
        cutoff = datetime.utcnow() - timedelta(minutes=window_minutes)
        recent_trades = [t for t in self.trade_history if t['timestamp'] > cutoff]
        
        if not recent_trades:
            return {'error': 'No recent trades'}
        
        # Calculate buy vs sell volume
        buy_volume = sum(t['volume'] for t in recent_trades if t['side'] == 'buy')
        sell_volume = sum(t['volume'] for t in recent_trades if t['side'] == 'sell')
        total_volume = buy_volume + sell_volume
        
        # Order flow imbalance ratio
        ofi = (buy_volume - sell_volume) / total_volume if total_volume > 0 else 0
        
        # Volume-weighted average prices
        buy_trades = [t for t in recent_trades if t['side'] == 'buy']
        sell_trades = [t for t in recent_trades if t['side'] == 'sell']
        
        vwap_buy = (
            sum(t['price'] * t['volume'] for t in buy_trades) / buy_volume
            if buy_volume > 0 else 0
        )
        vwap_sell = (
            sum(t['price'] * t['volume'] for t in sell_trades) / sell_volume
            if sell_volume > 0 else 0
        )
        
        return {
            'order_flow_imbalance': ofi,
            'buy_volume': buy_volume,
            'sell_volume': sell_volume,
            'total_volume': total_volume,
            'vwap_buy': vwap_buy,
            'vwap_sell': vwap_sell,
            'vwap_spread': vwap_buy - vwap_sell,
            'trade_count': len(recent_trades),
            'window_minutes': window_minutes,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def calculate_liquidity_metrics(self) -> Dict:
        """
        Calculate market liquidity metrics
        
        Returns:
            Comprehensive liquidity analysis
        """
        if len(self.quote_history) < 10:
            return {'error': 'Insufficient quote data'}
        
        recent_quotes = list(self.quote_history)[-50:]  # Last 50 quotes
        
        # Bid-ask spread statistics
        spreads = [q['spread'] for q in recent_quotes]
        spread_bps = [q['spread_bps'] for q in recent_quotes]
        
        # Depth at best bid/ask
        bid_sizes = [q['bid_size'] for q in recent_quotes]
        ask_sizes = [q['ask_size'] for q in recent_quotes]
        total_depth = [q['bid_size'] + q['ask_size'] for q in recent_quotes]
        
        # Price impact estimation (Kyle's lambda)
        # Simplified: spread / (2 * average depth)
        avg_spread = np.mean(spreads)
        avg_depth = np.mean(total_depth)
        kyle_lambda = (avg_spread / 2) / avg_depth if avg_depth > 0 else 0
        
        # Amihud illiquidity measure
        # |return| / volume (would need price changes and volumes)
        
        # Quote volatility
        mid_prices = [q['mid_price'] for q in recent_quotes]
        returns = np.diff(mid_prices) / mid_prices[:-1]
        price_volatility = np.std(returns) if len(returns) > 0 else 0
        
        return {
            'avg_spread': avg_spread,
            'avg_spread_bps': np.mean(spread_bps),
            'spread_volatility': np.std(spreads),
            'avg_bid_depth': np.mean(bid_sizes),
            'avg_ask_depth': np.mean(ask_sizes),
            'avg_total_depth': avg_depth,
            'depth_imbalance': (np.mean(bid_sizes) - np.mean(ask_sizes)) / avg_depth,
            'kyle_lambda': kyle_lambda,
            'quote_volatility': price_volatility,
            'resilience_score': 1.0 / kyle_lambda if kyle_lambda > 0 else 0,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def estimate_price_impact(
        self,
        order_size: int,
        direction: str  # 'buy' or 'sell'
    ) -> Dict:
        """
        Estimate price impact of a trade
        
        Args:
            order_size: Size of hypothetical order
            direction: 'buy' or 'sell'
            
        Returns:
            Price impact estimation
        """
        liquidity = self.calculate_liquidity_metrics()
        
        if 'error' in liquidity:
            return liquidity
        
        # Square root impact model
        # Impact = lambda * sqrt(order_size / avg_volume)
        recent_trades = list(self.trade_history)[-20:]
        avg_trade_size = np.mean([t['volume'] for t in recent_trades]) if recent_trades else 100
        
        normalized_size = order_size / avg_trade_size
        
        # Price impact (in basis points)
        temporary_impact = liquidity['kyle_lambda'] * np.sqrt(normalized_size) * 10000
        
        # Permanent impact (typically 30-50% of temporary)
        permanent_impact = temporary_impact * 0.4
        
        # Slippage estimate
        current_quote = list(self.quote_history)[-1] if self.quote_history else None
        
        if current_quote:
            mid_price = current_quote['mid_price']
            estimated_slippage_bps = temporary_impact
            estimated_fill_price = (
                mid_price * (1 + estimated_slippage_bps / 10000)
                if direction == 'buy'
                else mid_price * (1 - estimated_slippage_bps / 10000)
            )
        else:
            mid_price = None
            estimated_slippage_bps = None
            estimated_fill_price = None
        
        return {
            'order_size': order_size,
            'direction': direction,
            'temporary_impact_bps': temporary_impact,
            'permanent_impact_bps': permanent_impact,
            'total_impact_bps': temporary_impact + permanent_impact,
            'estimated_slippage_bps': estimated_slippage_bps,
            'mid_price': mid_price,
            'estimated_fill_price': estimated_fill_price,
            'market_depth_score': liquidity['avg_total_depth'],
            'liquidity_score': liquidity['resilience_score'],
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def analyze_volume_profile(
        self,
        price_bins: int = 20
    ) -> Dict:
        """
        Create volume profile analysis (Volume-at-Price)
        
        Args:
            price_bins: Number of price levels to analyze
            
        Returns:
            Volume profile data
        """
        if len(self.trade_history) < 20:
            return {'error': 'Insufficient trade data'}
        
        trades = list(self.trade_history)
        
        # Get price range
        prices = [t['price'] for t in trades]
        min_price = min(prices)
        max_price = max(prices)
        
        # Create price bins
        bin_edges = np.linspace(min_price, max_price, price_bins + 1)
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
        
        # Aggregate volume at each price level
        volume_profile = np.zeros(price_bins)
        buy_volume_profile = np.zeros(price_bins)
        sell_volume_profile = np.zeros(price_bins)
        
        for trade in trades:
            bin_idx = np.searchsorted(bin_edges[1:], trade['price'])
            bin_idx = min(bin_idx, price_bins - 1)
            
            volume_profile[bin_idx] += trade['volume']
            if trade['side'] == 'buy':
                buy_volume_profile[bin_idx] += trade['volume']
            else:
                sell_volume_profile[bin_idx] += trade['volume']
        
        # Find point of control (price with most volume)
        poc_idx = np.argmax(volume_profile)
        poc_price = bin_centers[poc_idx]
        
        # Value area (70% of volume)
        total_volume = volume_profile.sum()
        sorted_indices = np.argsort(volume_profile)[::-1]
        cumulative = 0
        value_area_indices = []
        
        for idx in sorted_indices:
            cumulative += volume_profile[idx]
            value_area_indices.append(idx)
            if cumulative >= total_volume * 0.70:
                break
        
        value_area_high = bin_centers[max(value_area_indices)]
        value_area_low = bin_centers[min(value_area_indices)]
        
        return {
            'point_of_control': poc_price,
            'value_area_high': value_area_high,
            'value_area_low': value_area_low,
            'value_area_range': value_area_high - value_area_low,
            'total_volume': total_volume,
            'price_levels': bin_centers.tolist(),
            'volume_at_price': volume_profile.tolist(),
            'buy_volume_at_price': buy_volume_profile.tolist(),
            'sell_volume_at_price': sell_volume_profile.tolist(),
            'imbalance_at_price': (buy_volume_profile - sell_volume_profile).tolist(),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def detect_aggressive_flow(self, sensitivity: float = 2.0) -> Dict:
        """
        Detect unusually aggressive buying or selling
        
        Args:
            sensitivity: Standard deviations for threshold
            
        Returns:
            Aggressive flow detection
        """
        if len(self.trade_history) < 50:
            return {'error': 'Insufficient data'}
        
        # Calculate rolling order flow imbalance
        window_size = 10
        ofi_series = []
        
        trades = list(self.trade_history)
        for i in range(window_size, len(trades)):
            window = trades[i-window_size:i]
            buy_vol = sum(t['volume'] for t in window if t['side'] == 'buy')
            sell_vol = sum(t['volume'] for t in window if t['side'] == 'sell')
            total_vol = buy_vol + sell_vol
            ofi = (buy_vol - sell_vol) / total_vol if total_vol > 0 else 0
            ofi_series.append(ofi)
        
        # Calculate statistics
        mean_ofi = np.mean(ofi_series)
        std_ofi = np.std(ofi_series)
        current_ofi = ofi_series[-1] if ofi_series else 0
        
        # Z-score
        z_score = (current_ofi - mean_ofi) / std_ofi if std_ofi > 0 else 0
        
        # Detect aggressive flow
        is_aggressive_buy = z_score > sensitivity
        is_aggressive_sell = z_score < -sensitivity
        
        return {
            'current_ofi': current_ofi,
            'mean_ofi': mean_ofi,
            'std_ofi': std_ofi,
            'z_score': z_score,
            'is_aggressive_buy': is_aggressive_buy,
            'is_aggressive_sell': is_aggressive_sell,
            'signal_strength': abs(z_score) / sensitivity,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def get_execution_quality_score(self) -> float:
        """
        Calculate overall execution quality score (0-100)
        Higher = better execution environment
        
        Returns:
            Execution quality score
        """
        liquidity = self.calculate_liquidity_metrics()
        
        if 'error' in liquidity:
            return 0.0
        
        # Components of execution quality
        
        # 1. Spread score (lower spread = better)
        # Normalize: 0 bps = 100, 50 bps = 0
        spread_score = max(0, 100 - (liquidity['avg_spread_bps'] / 50) * 100)
        
        # 2. Depth score (higher depth = better)
        # Normalize against typical depth of 500 contracts
        depth_score = min(100, (liquidity['avg_total_depth'] / 500) * 100)
        
        # 3. Volatility score (lower volatility = better)
        # Normalize: 0 vol = 100, high vol = 0
        vol_score = max(0, 100 - (liquidity['quote_volatility'] * 10000))
        
        # 4. Resilience score (higher resilience = better)
        resilience_score = min(100, liquidity['resilience_score'] * 10)
        
        # Weighted average
        weights = {'spread': 0.30, 'depth': 0.30, 'volatility': 0.20, 'resilience': 0.20}
        
        total_score = (
            spread_score * weights['spread'] +
            depth_score * weights['depth'] +
            vol_score * weights['volatility'] +
            resilience_score * weights['resilience']
        )
        
        return total_score


if __name__ == "__main__":
    # Example usage
    analyzer = MarketMicrostructureAnalyzer()
    
    # Simulate some market data
    base_price = 425.00
    for i in range(100):
        timestamp = datetime.utcnow() - timedelta(seconds=(100-i)*10)
        
        # Random walk price
        price = base_price + np.random.randn() * 2.0
        
        # Update quotes
        spread = 0.25 + np.random.rand() * 0.25
        analyzer.update_quote(
            timestamp=timestamp,
            bid_price=price - spread/2,
            bid_size=int(100 + np.random.rand() * 200),
            ask_price=price + spread/2,
            ask_size=int(100 + np.random.rand() * 200)
        )
        
        # Update trades
        if np.random.rand() > 0.5:
            analyzer.update_trade(
                timestamp=timestamp,
                price=price,
                volume=int(50 + np.random.rand() * 100),
                side='buy' if np.random.rand() > 0.5 else 'sell'
            )
    
    # Analyze
    print("Market Microstructure Analysis:")
    print("\n1. Order Flow:")
    print(analyzer.calculate_order_flow_imbalance())
    
    print("\n2. Liquidity Metrics:")
    print(analyzer.calculate_liquidity_metrics())
    
    print("\n3. Price Impact (1000 contracts):")
    print(analyzer.estimate_price_impact(1000, 'buy'))
    
    print("\n4. Execution Quality Score:")
    print(f"{analyzer.get_execution_quality_score():.2f}/100")
