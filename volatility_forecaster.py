"""
AgriQuant AI - Volatility Forecasting Models
GARCH, EWMA, and regime-switching volatility models for ag commodity futures
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from scipy import stats
from scipy.optimize import minimize
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VolatilityForecaster:
    """
    Advanced volatility forecasting for ag commodity futures
    - GARCH(1,1) model
    - EWMA (Exponentially Weighted Moving Average)
    - Regime-switching volatility
    - Realized volatility from high-frequency data
    """
    
    def __init__(self):
        # GARCH parameters
        self.garch_omega = None
        self.garch_alpha = None
        self.garch_beta = None
        
        # EWMA parameter
        self.ewma_lambda = 0.94  # RiskMetrics standard
        
        # Regime parameters
        self.regimes = ['low_vol', 'medium_vol', 'high_vol']
        self.current_regime = 'medium_vol'
    
    def calculate_realized_volatility(
        self,
        returns: np.ndarray,
        window: int = 20,
        annualization_factor: int = 252
    ) -> np.ndarray:
        """
        Calculate realized volatility from returns
        
        Args:
            returns: Array of returns
            window: Rolling window size
            annualization_factor: Trading days per year
            
        Returns:
            Realized volatility series
        """
        squared_returns = returns ** 2
        realized_var = pd.Series(squared_returns).rolling(window=window).mean()
        realized_vol = np.sqrt(realized_var * annualization_factor)
        
        return realized_vol.values
    
    def ewma_volatility(
        self,
        returns: np.ndarray,
        lambda_param: float = None
    ) -> np.ndarray:
        """
        EWMA (Exponentially Weighted Moving Average) volatility
        
        Args:
            returns: Returns series
            lambda_param: Decay parameter (default: 0.94)
            
        Returns:
            EWMA volatility forecast
        """
        if lambda_param is None:
            lambda_param = self.ewma_lambda
        
        # Initialize
        ewma_var = np.zeros(len(returns))
        ewma_var[0] = returns[0] ** 2
        
        # Recursive calculation
        for t in range(1, len(returns)):
            ewma_var[t] = lambda_param * ewma_var[t-1] + (1 - lambda_param) * returns[t-1] ** 2
        
        # Annualize and convert to volatility
        ewma_vol = np.sqrt(ewma_var * 252)
        
        return ewma_vol
    
    def garch_11_likelihood(
        self,
        params: np.ndarray,
        returns: np.ndarray
    ) -> float:
        """
        Negative log-likelihood for GARCH(1,1) estimation
        
        Args:
            params: [omega, alpha, beta]
            returns: Returns series
            
        Returns:
            Negative log-likelihood
        """
        omega, alpha, beta = params
        
        # Parameter constraints
        if omega <= 0 or alpha < 0 or beta < 0 or alpha + beta >= 1:
            return 1e10
        
        T = len(returns)
        sigma2 = np.zeros(T)
        sigma2[0] = np.var(returns)  # Initial variance
        
        # Recursively calculate conditional variance
        for t in range(1, T):
            sigma2[t] = omega + alpha * returns[t-1]**2 + beta * sigma2[t-1]
        
        # Log-likelihood (assuming normal distribution)
        log_likelihood = -0.5 * np.sum(
            np.log(2 * np.pi) + np.log(sigma2) + returns**2 / sigma2
        )
        
        return -log_likelihood  # Negative for minimization
    
    def fit_garch_11(
        self,
        returns: np.ndarray,
        initial_params: Optional[np.ndarray] = None
    ) -> Dict:
        """
        Fit GARCH(1,1) model to returns
        
        Args:
            returns: Returns series
            initial_params: Initial parameter guess [omega, alpha, beta]
            
        Returns:
            Fitted parameters and diagnostics
        """
        if initial_params is None:
            # Common initial values
            initial_params = np.array([0.0001, 0.05, 0.90])
        
        # Optimize
        result = minimize(
            fun=self.garch_11_likelihood,
            x0=initial_params,
            args=(returns,),
            method='L-BFGS-B',
            bounds=[(1e-6, None), (0, 1), (0, 1)]
        )
        
        if result.success:
            self.garch_omega, self.garch_alpha, self.garch_beta = result.x
            
            logger.info(
                f"GARCH(1,1) fitted: omega={self.garch_omega:.6f}, "
                f"alpha={self.garch_alpha:.6f}, beta={self.garch_beta:.6f}"
            )
        else:
            logger.warning("GARCH optimization failed")
        
        # Calculate fitted conditional volatility
        T = len(returns)
        conditional_var = np.zeros(T)
        conditional_var[0] = np.var(returns)
        
        for t in range(1, T):
            conditional_var[t] = (
                self.garch_omega +
                self.garch_alpha * returns[t-1]**2 +
                self.garch_beta * conditional_var[t-1]
            )
        
        conditional_vol = np.sqrt(conditional_var * 252)  # Annualized
        
        return {
            'omega': self.garch_omega,
            'alpha': self.garch_alpha,
            'beta': self.garch_beta,
            'persistence': self.garch_alpha + self.garch_beta,
            'unconditional_variance': self.garch_omega / (1 - self.garch_alpha - self.garch_beta),
            'conditional_volatility': conditional_vol,
            'success': result.success
        }
    
    def forecast_garch_volatility(
        self,
        last_return: float,
        last_variance: float,
        horizon: int = 20
    ) -> np.ndarray:
        """
        Forecast volatility using fitted GARCH model
        
        Args:
            last_return: Most recent return
            last_variance: Most recent conditional variance
            horizon: Forecast horizon in days
            
        Returns:
            Volatility forecast for each day
        """
        if self.garch_omega is None:
            raise ValueError("GARCH model not fitted. Call fit_garch_11() first.")
        
        forecasts = np.zeros(horizon)
        
        # Day 1 forecast
        var_forecast = (
            self.garch_omega +
            self.garch_alpha * last_return**2 +
            self.garch_beta * last_variance
        )
        forecasts[0] = np.sqrt(var_forecast * 252)
        
        # Multi-step ahead forecasts
        unconditional_var = self.garch_omega / (1 - self.garch_alpha - self.garch_beta)
        persistence = self.garch_alpha + self.garch_beta
        
        for h in range(1, horizon):
            var_forecast = (
                unconditional_var +
                persistence**h * (var_forecast - unconditional_var)
            )
            forecasts[h] = np.sqrt(var_forecast * 252)
        
        return forecasts
    
    def detect_volatility_regime(
        self,
        current_volatility: float,
        historical_volatility: np.ndarray
    ) -> Dict:
        """
        Detect current volatility regime
        
        Args:
            current_volatility: Current volatility level
            historical_volatility: Historical volatility series
            
        Returns:
            Regime detection results
        """
        # Calculate percentiles
        p25 = np.percentile(historical_volatility, 25)
        p75 = np.percentile(historical_volatility, 75)
        
        # Classify regime
        if current_volatility < p25:
            regime = 'low_vol'
            regime_score = 0.0
        elif current_volatility > p75:
            regime = 'high_vol'
            regime_score = 1.0
        else:
            regime = 'medium_vol'
            regime_score = 0.5
        
        self.current_regime = regime
        
        # Calculate regime transition probability
        # Using simple threshold crossing probability
        z_score = (current_volatility - np.mean(historical_volatility)) / np.std(historical_volatility)
        
        return {
            'current_regime': regime,
            'regime_score': regime_score,
            'volatility_percentile': stats.percentileofscore(historical_volatility, current_volatility),
            'z_score': z_score,
            'threshold_low': p25,
            'threshold_high': p75,
            'mean_volatility': np.mean(historical_volatility),
            'std_volatility': np.std(historical_volatility)
        }
    
    def calculate_parkinson_volatility(
        self,
        high_prices: np.ndarray,
        low_prices: np.ndarray
    ) -> float:
        """
        Parkinson volatility estimator (uses high-low range)
        More efficient than close-to-close for range data
        
        Args:
            high_prices: High prices
            low_prices: Low prices
            
        Returns:
            Parkinson volatility estimate
        """
        hl_ratio = np.log(high_prices / low_prices)
        parkinson_var = np.mean(hl_ratio ** 2) / (4 * np.log(2))
        parkinson_vol = np.sqrt(parkinson_var * 252)  # Annualized
        
        return parkinson_vol
    
    def calculate_garman_klass_volatility(
        self,
        open_prices: np.ndarray,
        high_prices: np.ndarray,
        low_prices: np.ndarray,
        close_prices: np.ndarray
    ) -> float:
        """
        Garman-Klass volatility estimator
        Most efficient estimator using OHLC data
        
        Args:
            open_prices: Opening prices
            high_prices: High prices
            low_prices: Low prices
            close_prices: Closing prices
            
        Returns:
            Garman-Klass volatility estimate
        """
        hl = np.log(high_prices / low_prices)
        co = np.log(close_prices / open_prices)
        
        gk_var = 0.5 * np.mean(hl ** 2) - (2 * np.log(2) - 1) * np.mean(co ** 2)
        gk_vol = np.sqrt(gk_var * 252)  # Annualized
        
        return gk_vol
    
    def ensemble_volatility_forecast(
        self,
        returns: np.ndarray,
        high_prices: np.ndarray,
        low_prices: np.ndarray,
        open_prices: np.ndarray,
        close_prices: np.ndarray,
        forecast_horizon: int = 20
    ) -> Dict:
        """
        Combine multiple volatility models for robust forecast
        
        Args:
            returns: Returns series
            high_prices: High prices
            low_prices: Low prices
            open_prices: Opening prices
            close_prices: Closing prices
            forecast_horizon: Days ahead to forecast
            
        Returns:
            Ensemble forecast with individual model contributions
        """
        # 1. Historical (realized) volatility
        realized_vol = self.calculate_realized_volatility(returns)
        hist_forecast = realized_vol[-1]  # Use most recent
        
        # 2. EWMA volatility
        ewma_vol = self.ewma_volatility(returns)
        ewma_forecast = ewma_vol[-1]
        
        # 3. GARCH volatility
        garch_fit = self.fit_garch_11(returns)
        if garch_fit['success']:
            garch_forecasts = self.forecast_garch_volatility(
                last_return=returns[-1],
                last_variance=garch_fit['conditional_volatility'][-1]**2 / 252,
                horizon=forecast_horizon
            )
            garch_forecast = garch_forecasts[0]
        else:
            garch_forecast = hist_forecast
            garch_forecasts = np.full(forecast_horizon, hist_forecast)
        
        # 4. Parkinson estimator
        parkinson_forecast = self.calculate_parkinson_volatility(high_prices, low_prices)
        
        # 5. Garman-Klass estimator
        gk_forecast = self.calculate_garman_klass_volatility(
            open_prices, high_prices, low_prices, close_prices
        )
        
        # Ensemble weights (based on typical forecasting accuracy)
        weights = {
            'garch': 0.35,
            'ewma': 0.25,
            'garman_klass': 0.20,
            'parkinson': 0.12,
            'historical': 0.08
        }
        
        # Combined forecast
        ensemble_forecast = (
            weights['garch'] * garch_forecast +
            weights['ewma'] * ewma_forecast +
            weights['garman_klass'] * gk_forecast +
            weights['parkinson'] * parkinson_forecast +
            weights['historical'] * hist_forecast
        )
        
        # Forecast uncertainty (std of individual forecasts)
        individual_forecasts = [
            garch_forecast, ewma_forecast, gk_forecast,
            parkinson_forecast, hist_forecast
        ]
        forecast_std = np.std(individual_forecasts)
        
        # Detect regime
        regime_info = self.detect_volatility_regime(
            current_volatility=ensemble_forecast,
            historical_volatility=realized_vol[~np.isnan(realized_vol)]
        )
        
        return {
            'ensemble_forecast': ensemble_forecast,
            'forecast_std': forecast_std,
            'confidence_95_lower': ensemble_forecast - 1.96 * forecast_std,
            'confidence_95_upper': ensemble_forecast + 1.96 * forecast_std,
            'individual_forecasts': {
                'garch': garch_forecast,
                'ewma': ewma_forecast,
                'garman_klass': gk_forecast,
                'parkinson': parkinson_forecast,
                'historical': hist_forecast
            },
            'garch_forecast_path': garch_forecasts.tolist(),
            'regime': regime_info['current_regime'],
            'regime_percentile': regime_info['volatility_percentile'],
            'model_weights': weights,
            'timestamp': datetime.utcnow().isoformat()
        }


if __name__ == "__main__":
    # Example usage
    forecaster = VolatilityForecaster()
    
    # Generate synthetic data
    np.random.seed(42)
    T = 500
    
    # Simulate GARCH process
    omega, alpha, beta = 0.0001, 0.08, 0.90
    returns = np.zeros(T)
    variance = np.zeros(T)
    variance[0] = 0.0001
    
    for t in range(1, T):
        variance[t] = omega + alpha * returns[t-1]**2 + beta * variance[t-1]
        returns[t] = np.sqrt(variance[t]) * np.random.randn()
    
    # Simulate OHLC
    prices = 425 + np.cumsum(returns * 10)
    high_prices = prices + np.abs(np.random.randn(T)) * 2
    low_prices = prices - np.abs(np.random.randn(T)) * 2
    open_prices = prices + np.random.randn(T) * 0.5
    close_prices = prices
    
    print("Volatility Forecasting Models")
    print("=" * 50)
    
    # Fit GARCH
    garch_fit = forecaster.fit_garch_11(returns)
    print(f"\nGARCH(1,1) Parameters:")
    print(f"  omega: {garch_fit['omega']:.6f}")
    print(f"  alpha: {garch_fit['alpha']:.6f}")
    print(f"  beta: {garch_fit['beta']:.6f}")
    print(f"  persistence: {garch_fit['persistence']:.6f}")
    
    # Ensemble forecast
    forecast = forecaster.ensemble_volatility_forecast(
        returns=returns,
        high_prices=high_prices,
        low_prices=low_prices,
        open_prices=open_prices,
        close_prices=close_prices,
        forecast_horizon=20
    )
    
    print(f"\nEnsemble Volatility Forecast:")
    print(f"  Forecast: {forecast['ensemble_forecast']:.2f}%")
    print(f"  95% CI: [{forecast['confidence_95_lower']:.2f}%, {forecast['confidence_95_upper']:.2f}%]")
    print(f"  Regime: {forecast['regime']}")
    print(f"  Percentile: {forecast['regime_percentile']:.1f}%")
