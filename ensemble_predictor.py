"""
AgriQuant AI - Multi-Model Price Prediction Engine
Ensemble approach combining multiple prediction models for ag commodity futures
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import Ridge, Lasso
from sklearn.preprocessing import StandardScaler
import joblib
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EnsemblePricePredictor:
    """
    Sophisticated ensemble prediction model for ag commodity futures prices
    Combines weather impact, seasonal patterns, and market dynamics
    """
    
    def __init__(self, models_path: str = "models/"):
        self.models_path = models_path
        self.scaler = StandardScaler()
        
        # Individual models
        self.rf_model = RandomForestRegressor(
            n_estimators=200,
            max_depth=15,
            min_samples_split=5,
            random_state=42
        )
        self.gb_model = GradientBoostingRegressor(
            n_estimators=150,
            learning_rate=0.05,
            max_depth=8,
            random_state=42
        )
        self.ridge_model = Ridge(alpha=1.0)
        self.lasso_model = Lasso(alpha=0.1)
        
        # Model weights (learned from validation performance)
        self.model_weights = {
            'random_forest': 0.35,
            'gradient_boosting': 0.30,
            'ridge': 0.20,
            'lasso': 0.15
        }
        
    def extract_features(
        self,
        weather_data: Dict,
        market_data: Dict,
        seasonal_data: Dict
    ) -> np.ndarray:
        """
        Extract comprehensive feature set for prediction
        
        Args:
            weather_data: Current and forecasted weather conditions
            market_data: Recent ag commodity futures prices and volumes
            seasonal_data: Historical seasonal patterns
            
        Returns:
            Feature vector for model input
        """
        features = []
        
        # Weather features (20 features)
        features.extend([
            weather_data.get('temp_min_7day', 0),
            weather_data.get('temp_max_7day', 0),
            weather_data.get('temp_mean_7day', 0),
            weather_data.get('freeze_probability', 0),
            weather_data.get('frost_hours_expected', 0),
            weather_data.get('precipitation_7day', 0),
            weather_data.get('humidity_mean', 0),
            weather_data.get('wind_speed_max', 0),
            weather_data.get('gdd_cumulative', 0),  # Growing degree days
            weather_data.get('chill_hours_cumulative', 0),
            weather_data.get('ndvi_polk', 0),
            weather_data.get('ndvi_highlands', 0),
            weather_data.get('ndvi_desoto', 0),
            weather_data.get('ndvi_hardee', 0),
            weather_data.get('soil_moisture_polk', 0),
            weather_data.get('drought_index', 0),
            weather_data.get('hurricane_probability', 0),
            weather_data.get('disease_pressure_index', 0),
            weather_data.get('evapotranspiration', 0),
            weather_data.get('solar_radiation', 0)
        ])
        
        # Market features (15 features)
        features.extend([
            market_data.get('price_current', 0),
            market_data.get('price_ma_5', 0),
            market_data.get('price_ma_20', 0),
            market_data.get('price_ma_50', 0),
            market_data.get('rsi_14', 0),
            market_data.get('atr_14', 0),
            market_data.get('volume_ma_20', 0),
            market_data.get('volume_current', 0),
            market_data.get('open_interest', 0),
            market_data.get('basis_nearby_deferred', 0),
            market_data.get('volatility_30day', 0),
            market_data.get('momentum_10day', 0),
            market_data.get('bollinger_position', 0),
            market_data.get('macd', 0),
            market_data.get('macd_signal', 0)
        ])
        
        # Seasonal features (10 features)
        features.extend([
            seasonal_data.get('month', 0),
            seasonal_data.get('day_of_year', 0),
            seasonal_data.get('harvest_season', 0),  # Binary
            seasonal_data.get('freeze_season', 0),  # Binary
            seasonal_data.get('hurricane_season', 0),  # Binary
            seasonal_data.get('avg_price_this_month_historical', 0),
            seasonal_data.get('avg_volatility_this_month_historical', 0),
            seasonal_data.get('crop_stage', 0),  # 0-1 representing growth stage
            seasonal_data.get('days_to_harvest', 0),
            seasonal_data.get('historical_freeze_frequency', 0)
        ])
        
        # Economic features (5 features)
        features.extend([
            seasonal_data.get('brazil_production_forecast', 0),
            seasonal_data.get('global_demand_index', 0),
            seasonal_data.get('usd_index', 0),
            seasonal_data.get('crude_oil_price', 0),  # Correlated commodity
            seasonal_data.get('consumer_sentiment', 0)
        ])
        
        return np.array(features).reshape(1, -1)
    
    def train_models(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray
    ) -> Dict[str, float]:
        """
        Train all models in the ensemble
        
        Args:
            X_train: Training features
            y_train: Training targets (price changes)
            X_val: Validation features
            y_val: Validation targets
            
        Returns:
            Validation performance metrics
        """
        logger.info("Training ensemble models...")
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_val_scaled = self.scaler.transform(X_val)
        
        # Train individual models
        self.rf_model.fit(X_train_scaled, y_train)
        self.gb_model.fit(X_train_scaled, y_train)
        self.ridge_model.fit(X_train_scaled, y_train)
        self.lasso_model.fit(X_train_scaled, y_train)
        
        # Evaluate on validation set
        rf_pred = self.rf_model.predict(X_val_scaled)
        gb_pred = self.gb_model.predict(X_val_scaled)
        ridge_pred = self.ridge_model.predict(X_val_scaled)
        lasso_pred = self.lasso_model.predict(X_val_scaled)
        
        # Calculate individual model performance
        from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
        
        metrics = {
            'random_forest': {
                'mse': mean_squared_error(y_val, rf_pred),
                'mae': mean_absolute_error(y_val, rf_pred),
                'r2': r2_score(y_val, rf_pred)
            },
            'gradient_boosting': {
                'mse': mean_squared_error(y_val, gb_pred),
                'mae': mean_absolute_error(y_val, gb_pred),
                'r2': r2_score(y_val, gb_pred)
            },
            'ridge': {
                'mse': mean_squared_error(y_val, ridge_pred),
                'mae': mean_absolute_error(y_val, ridge_pred),
                'r2': r2_score(y_val, ridge_pred)
            },
            'lasso': {
                'mse': mean_squared_error(y_val, lasso_pred),
                'mae': mean_absolute_error(y_val, lasso_pred),
                'r2': r2_score(y_val, lasso_pred)
            }
        }
        
        # Ensemble prediction
        ensemble_pred = (
            rf_pred * self.model_weights['random_forest'] +
            gb_pred * self.model_weights['gradient_boosting'] +
            ridge_pred * self.model_weights['ridge'] +
            lasso_pred * self.model_weights['lasso']
        )
        
        metrics['ensemble'] = {
            'mse': mean_squared_error(y_val, ensemble_pred),
            'mae': mean_absolute_error(y_val, ensemble_pred),
            'r2': r2_score(y_val, ensemble_pred)
        }
        
        logger.info(f"Ensemble R²: {metrics['ensemble']['r2']:.4f}")
        
        # Save models
        self.save_models()
        
        return metrics
    
    def predict_price_movement(
        self,
        weather_data: Dict,
        market_data: Dict,
        seasonal_data: Dict,
        horizon_days: int = 7
    ) -> Dict:
        """
        Predict ag commodity futures price movement
        
        Args:
            weather_data: Current weather conditions and forecast
            market_data: Current market state
            seasonal_data: Seasonal patterns
            horizon_days: Prediction horizon (1-14 days)
            
        Returns:
            Prediction with confidence intervals
        """
        # Extract features
        features = self.extract_features(weather_data, market_data, seasonal_data)
        features_scaled = self.scaler.transform(features)
        
        # Get predictions from all models
        rf_pred = self.rf_model.predict(features_scaled)[0]
        gb_pred = self.gb_model.predict(features_scaled)[0]
        ridge_pred = self.ridge_model.predict(features_scaled)[0]
        lasso_pred = self.lasso_model.predict(features_scaled)[0]
        
        # Ensemble prediction (weighted average)
        ensemble_pred = (
            rf_pred * self.model_weights['random_forest'] +
            gb_pred * self.model_weights['gradient_boosting'] +
            ridge_pred * self.model_weights['ridge'] +
            lasso_pred * self.model_weights['lasso']
        )
        
        # Calculate prediction uncertainty (std of individual predictions)
        predictions = [rf_pred, gb_pred, ridge_pred, lasso_pred]
        pred_std = np.std(predictions)
        
        # Confidence intervals (assuming normal distribution)
        confidence_95_lower = ensemble_pred - 1.96 * pred_std
        confidence_95_upper = ensemble_pred + 1.96 * pred_std
        
        # Model agreement score (lower std = higher agreement)
        max_disagreement = max(predictions) - min(predictions)
        agreement_score = 1.0 - min(max_disagreement / abs(ensemble_pred), 1.0) if ensemble_pred != 0 else 0
        
        return {
            'predicted_change_pct': ensemble_pred,
            'confidence_95_lower': confidence_95_lower,
            'confidence_95_upper': confidence_95_upper,
            'prediction_std': pred_std,
            'model_agreement': agreement_score,
            'horizon_days': horizon_days,
            'individual_predictions': {
                'random_forest': rf_pred,
                'gradient_boosting': gb_pred,
                'ridge': ridge_pred,
                'lasso': lasso_pred
            },
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def calculate_trading_signal(
        self,
        prediction: Dict,
        current_price: float,
        confidence_threshold: float = 0.70
    ) -> Dict:
        """
        Convert price prediction into trading signal
        
        Args:
            prediction: Output from predict_price_movement()
            current_price: Current ag commodity futures price
            confidence_threshold: Minimum model agreement for trade
            
        Returns:
            Trading signal with position size recommendation
        """
        pred_change = prediction['predicted_change_pct']
        agreement = prediction['model_agreement']
        
        # No trade if low model agreement
        if agreement < confidence_threshold:
            return {
                'signal': 'NO_TRADE',
                'reason': 'Low model agreement',
                'position_size_pct': 0,
                'expected_change_pct': pred_change,
                'confidence': agreement
            }
        
        # Determine direction
        if abs(pred_change) < 0.02:  # Less than 2% expected move
            return {
                'signal': 'NO_TRADE',
                'reason': 'Insufficient expected movement',
                'position_size_pct': 0,
                'expected_change_pct': pred_change,
                'confidence': agreement
            }
        
        # Calculate position size (scale with confidence and expected move)
        base_position = 0.20  # 20% of capital
        confidence_multiplier = (agreement - confidence_threshold) / (1.0 - confidence_threshold)
        magnitude_multiplier = min(abs(pred_change) / 0.10, 1.0)  # Cap at 10% expected move
        
        position_size = base_position * confidence_multiplier * magnitude_multiplier
        position_size = min(position_size, 0.30)  # Max 30% of capital
        
        signal = 'LONG' if pred_change > 0 else 'SHORT'
        
        # Calculate entry and exit targets
        expected_price = current_price * (1 + pred_change / 100)
        stop_loss_pct = -0.15  # 15% stop loss
        stop_loss_price = current_price * (1 + stop_loss_pct / 100) if signal == 'LONG' else current_price * (1 - stop_loss_pct / 100)
        
        return {
            'signal': signal,
            'position_size_pct': position_size,
            'entry_price': current_price,
            'target_price': expected_price,
            'stop_loss_price': stop_loss_price,
            'expected_change_pct': pred_change,
            'confidence': agreement,
            'risk_reward_ratio': abs(pred_change) / abs(stop_loss_pct),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def save_models(self):
        """Save trained models to disk"""
        import os
        os.makedirs(self.models_path, exist_ok=True)
        
        joblib.dump(self.rf_model, f"{self.models_path}/rf_model.pkl")
        joblib.dump(self.gb_model, f"{self.models_path}/gb_model.pkl")
        joblib.dump(self.ridge_model, f"{self.models_path}/ridge_model.pkl")
        joblib.dump(self.lasso_model, f"{self.models_path}/lasso_model.pkl")
        joblib.dump(self.scaler, f"{self.models_path}/scaler.pkl")
        joblib.dump(self.model_weights, f"{self.models_path}/weights.pkl")
        
        logger.info(f"Models saved to {self.models_path}")
    
    def load_models(self):
        """Load pre-trained models from disk"""
        self.rf_model = joblib.load(f"{self.models_path}/rf_model.pkl")
        self.gb_model = joblib.load(f"{self.models_path}/gb_model.pkl")
        self.ridge_model = joblib.load(f"{self.models_path}/ridge_model.pkl")
        self.lasso_model = joblib.load(f"{self.models_path}/lasso_model.pkl")
        self.scaler = joblib.load(f"{self.models_path}/scaler.pkl")
        self.model_weights = joblib.load(f"{self.models_path}/weights.pkl")
        
        logger.info("Models loaded successfully")


if __name__ == "__main__":
    # Example usage
    predictor = EnsemblePricePredictor()
    
    # Mock data for demonstration
    weather_data = {
        'temp_min_7day': 28.0,
        'temp_max_7day': 75.0,
        'temp_mean_7day': 55.0,
        'freeze_probability': 0.15,
        'frost_hours_expected': 8,
        'precipitation_7day': 0.5,
        'humidity_mean': 65,
        'wind_speed_max': 15,
        'gdd_cumulative': 1200,
        'chill_hours_cumulative': 450,
        'ndvi_polk': 0.75,
        'ndvi_highlands': 0.72,
        'ndvi_desoto': 0.78,
        'ndvi_hardee': 0.74,
        'soil_moisture_polk': 0.45,
        'drought_index': 0.2,
        'hurricane_probability': 0.05,
        'disease_pressure_index': 0.3,
        'evapotranspiration': 4.5,
        'solar_radiation': 450
    }
    
    market_data = {
        'price_current': 425.50,
        'price_ma_5': 420.30,
        'price_ma_20': 415.00,
        'price_ma_50': 410.00,
        'rsi_14': 58,
        'atr_14': 12.5,
        'volume_ma_20': 15000,
        'volume_current': 18000,
        'open_interest': 45000,
        'basis_nearby_deferred': 5.50,
        'volatility_30day': 0.25,
        'momentum_10day': 0.03,
        'bollinger_position': 0.65,
        'macd': 2.5,
        'macd_signal': 1.8
    }
    
    seasonal_data = {
        'month': 1,
        'day_of_year': 15,
        'harvest_season': 0,
        'freeze_season': 1,
        'hurricane_season': 0,
        'avg_price_this_month_historical': 420.0,
        'avg_volatility_this_month_historical': 0.22,
        'crop_stage': 0.65,
        'days_to_harvest': 120,
        'historical_freeze_frequency': 0.35,
        'brazil_production_forecast': 1.2,
        'global_demand_index': 105,
        'usd_index': 102.5,
        'crude_oil_price': 75.50,
        'consumer_sentiment': 98.5
    }
    
    # Make prediction (would normally load pre-trained models)
    # prediction = predictor.predict_price_movement(weather_data, market_data, seasonal_data)
    # print("Price Movement Prediction:")
    # print(json.dumps(prediction, indent=2))
    
    # Generate trading signal
    # signal = predictor.calculate_trading_signal(prediction, market_data['price_current'])
    # print("\nTrading Signal:")
    # print(json.dumps(signal, indent=2))
    
    print("Ensemble Price Predictor initialized")
    print("Features: 50 (20 weather + 15 market + 10 seasonal + 5 economic)")
    print("Models: 4 (Random Forest, Gradient Boosting, Ridge, Lasso)")
