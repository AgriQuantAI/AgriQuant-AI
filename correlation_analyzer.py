"""
AgriQuant AI - Multi-Asset Correlation Analyzer
Analyzes correlations between weather, ag commodity futures, and related markets
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
from datetime import datetime, timedelta
from scipy.stats import pearsonr, spearmanr
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CorrelationAnalyzer:
    """
    Analyzes correlations and dependencies across multiple time series:
    - Weather variables vs OJ prices
    - OJ vs related commodities (sugar, coffee, cocoa)
    - Dynamic correlation tracking
    - Lead-lag relationships
    """
    
    def __init__(self, lookback_days: int = 252):
        self.lookback_days = lookback_days
        self.correlation_history = []
    
    def calculate_rolling_correlation(
        self,
        series1: np.ndarray,
        series2: np.ndarray,
        window: int = 60
    ) -> np.ndarray:
        """
        Calculate rolling correlation between two series
        
        Args:
            series1: First time series
            series2: Second time series
            window: Rolling window size
            
        Returns:
            Rolling correlation series
        """
        df = pd.DataFrame({'x': series1, 'y': series2})
        rolling_corr = df['x'].rolling(window=window).corr(df['y'])
        return rolling_corr.values
    
    def weather_price_correlation(
        self,
        temperature: np.ndarray,
        precipitation: np.ndarray,
        freeze_days: np.ndarray,
        oj_returns: np.ndarray
    ) -> Dict:
        """
        Analyze correlation between weather variables and OJ returns
        
        Args:
            temperature: Daily temperature series
            precipitation: Daily precipitation
            freeze_days: Binary freeze indicator
            oj_returns: ag commodity futures returns
            
        Returns:
            Correlation analysis results
        """
        # Ensure same length
        min_len = min(len(temperature), len(precipitation), len(freeze_days), len(oj_returns))
        temp = temperature[-min_len:]
        precip = precipitation[-min_len:]
        freeze = freeze_days[-min_len:]
        returns = oj_returns[-min_len:]
        
        # Calculate correlations
        temp_corr, temp_pval = pearsonr(temp, returns)
        precip_corr, precip_pval = pearsonr(precip, returns)
        freeze_corr, freeze_pval = pearsonr(freeze, returns)
        
        # Lagged correlations (weather leads price)
        lags = [1, 3, 5, 7, 14]
        temp_lag_corrs = {}
        freeze_lag_corrs = {}
        
        for lag in lags:
            if lag < len(returns):
                temp_lag, _ = pearsonr(temp[:-lag], returns[lag:])
                freeze_lag, _ = pearsonr(freeze[:-lag], returns[lag:])
                temp_lag_corrs[f'lag_{lag}d'] = temp_lag
                freeze_lag_corrs[f'lag_{lag}d'] = freeze_lag
        
        return {
            'temperature_correlation': temp_corr,
            'temperature_pvalue': temp_pval,
            'precipitation_correlation': precip_corr,
            'precipitation_pvalue': precip_pval,
            'freeze_correlation': freeze_corr,
            'freeze_pvalue': freeze_pval,
            'temperature_lagged': temp_lag_corrs,
            'freeze_lagged': freeze_lag_corrs,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def cross_commodity_correlation(
        self,
        oj_prices: np.ndarray,
        sugar_prices: np.ndarray,
        coffee_prices: np.ndarray,
        cocoa_prices: np.ndarray
    ) -> Dict:
        """
        Analyze correlations with related soft commodities
        
        Args:
            oj_prices: ag commodity futures prices
            sugar_prices: Sugar futures prices
            coffee_prices: Coffee futures prices
            cocoa_prices: Cocoa futures prices
            
        Returns:
            Cross-commodity correlation matrix
        """
        # Calculate returns
        oj_ret = np.diff(np.log(oj_prices))
        sugar_ret = np.diff(np.log(sugar_prices))
        coffee_ret = np.diff(np.log(coffee_prices))
        cocoa_ret = np.diff(np.log(cocoa_prices))
        
        # Ensure same length
        min_len = min(len(oj_ret), len(sugar_ret), len(coffee_ret), len(cocoa_ret))
        oj_ret = oj_ret[-min_len:]
        sugar_ret = sugar_ret[-min_len:]
        coffee_ret = coffee_ret[-min_len:]
        cocoa_ret = cocoa_ret[-min_len:]
        
        # Correlation matrix
        corr_matrix = np.corrcoef([oj_ret, sugar_ret, coffee_ret, cocoa_ret])
        
        # Specific pair correlations
        oj_sugar, _ = pearsonr(oj_ret, sugar_ret)
        oj_coffee, _ = pearsonr(oj_ret, coffee_ret)
        oj_cocoa, _ = pearsonr(oj_ret, cocoa_ret)
        
        # Rolling correlations
        oj_sugar_rolling = self.calculate_rolling_correlation(oj_ret, sugar_ret, window=60)
        
        return {
            'correlation_matrix': corr_matrix.tolist(),
            'oj_sugar': oj_sugar,
            'oj_coffee': oj_coffee,
            'oj_cocoa': oj_cocoa,
            'oj_sugar_current': oj_sugar_rolling[-1] if len(oj_sugar_rolling) > 0 else None,
            'oj_sugar_mean': np.nanmean(oj_sugar_rolling),
            'oj_sugar_std': np.nanstd(oj_sugar_rolling),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def regime_dependent_correlation(
        self,
        returns1: np.ndarray,
        returns2: np.ndarray,
        volatility: np.ndarray
    ) -> Dict:
        """
        Calculate correlations conditional on volatility regime
        
        Args:
            returns1: First returns series
            returns2: Second returns series
            volatility: Volatility measure
            
        Returns:
            Regime-dependent correlations
        """
        # Define volatility regimes
        vol_25 = np.percentile(volatility, 25)
        vol_75 = np.percentile(volatility, 75)
        
        # Split into regimes
        low_vol_mask = volatility < vol_25
        med_vol_mask = (volatility >= vol_25) & (volatility <= vol_75)
        high_vol_mask = volatility > vol_75
        
        # Calculate correlations by regime
        corr_low, _ = pearsonr(returns1[low_vol_mask], returns2[low_vol_mask])
        corr_med, _ = pearsonr(returns1[med_vol_mask], returns2[med_vol_mask])
        corr_high, _ = pearsonr(returns1[high_vol_mask], returns2[high_vol_mask])
        
        return {
            'correlation_low_vol': corr_low,
            'correlation_medium_vol': corr_med,
            'correlation_high_vol': corr_high,
            'correlation_difference': corr_high - corr_low,
            'sample_size_low': int(low_vol_mask.sum()),
            'sample_size_medium': int(med_vol_mask.sum()),
            'sample_size_high': int(high_vol_mask.sum())
        }
    
    def calculate_beta(
        self,
        asset_returns: np.ndarray,
        market_returns: np.ndarray
    ) -> Dict:
        """
        Calculate beta (systematic risk) of OJ vs broader market
        
        Args:
            asset_returns: OJ returns
            market_returns: Market returns (e.g., S&P 500)
            
        Returns:
            Beta and related metrics
        """
        # Ensure same length
        min_len = min(len(asset_returns), len(market_returns))
        asset_ret = asset_returns[-min_len:]
        market_ret = market_returns[-min_len:]
        
        # Calculate beta
        covariance = np.cov(asset_ret, market_ret)[0, 1]
        market_variance = np.var(market_ret)
        beta = covariance / market_variance if market_variance > 0 else 0
        
        # Calculate alpha (excess return)
        mean_asset = np.mean(asset_ret)
        mean_market = np.mean(market_ret)
        alpha = mean_asset - beta * mean_market
        
        # R-squared
        correlation, _ = pearsonr(asset_ret, market_ret)
        r_squared = correlation ** 2
        
        # Tracking error
        predicted_returns = alpha + beta * market_ret
        tracking_error = np.std(asset_ret - predicted_returns)
        
        return {
            'beta': beta,
            'alpha_daily': alpha,
            'alpha_annualized': alpha * 252,
            'r_squared': r_squared,
            'correlation': correlation,
            'tracking_error': tracking_error * np.sqrt(252),
            'systematic_risk_pct': r_squared * 100,
            'idiosyncratic_risk_pct': (1 - r_squared) * 100
        }


if __name__ == "__main__":
    analyzer = CorrelationAnalyzer()
    
    # Generate synthetic data
    np.random.seed(42)
    T = 500
    
    temperature = 60 + 15 * np.sin(np.linspace(0, 4*np.pi, T)) + np.random.randn(T) * 5
    freeze_days = (temperature < 32).astype(int)
    oj_returns = 0.001 * np.random.randn(T) - 0.02 * freeze_days
    
    print("Correlation Analysis:")
    print("=" * 50)
    
    weather_corr = analyzer.weather_price_correlation(
        temperature=temperature,
        precipitation=np.random.rand(T) * 2,
        freeze_days=freeze_days,
        oj_returns=oj_returns
    )
    
    print(f"\nWeather-Price Correlations:")
    print(f"  Temperature: {weather_corr['temperature_correlation']:.3f}")
    print(f"  Freeze days: {weather_corr['freeze_correlation']:.3f}")
    print(f"  Lagged correlations: {weather_corr['freeze_lagged']}")
