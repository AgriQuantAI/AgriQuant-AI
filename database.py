"""
AgriQuant AI - Database Module
Stores weather data, predictions, USDA reports, and performance metrics
"""

import psycopg2
from psycopg2.extras import Json, RealDictCursor
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
from config import *

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AgriQuant AIDatabase:
    """
    PostgreSQL database for storing all AgriQuant AI data
    """
    
    def __init__(self, connection_string: str = None):
        self.connection_string = connection_string or DATABASE_URL
        self.conn = None
        self.cursor = None
    
    def connect(self):
        """Establish database connection"""
        try:
            self.conn = psycopg2.connect(self.connection_string)
            self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)
            logger.info("Database connection established")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise
    
    def disconnect(self):
        """Close database connection"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        logger.info("Database connection closed")
    
    def create_tables(self):
        """Create all necessary tables"""
        
        # Weather forecasts table
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS weather_forecasts (
                id SERIAL PRIMARY KEY,
                county VARCHAR(50) NOT NULL,
                forecast_time TIMESTAMP NOT NULL,
                data JSONB NOT NULL,
                freeze_risk VARCHAR(50),
                max_expected_damage FLOAT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        # Create index for fast queries
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_forecasts_county_time 
            ON weather_forecasts(county, forecast_time DESC)
        """)
        
        # Historical weather events table
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS historical_events (
                id SERIAL PRIMARY KEY,
                event_date DATE NOT NULL,
                event_type VARCHAR(50) NOT NULL,
                county VARCHAR(50),
                min_temperature FLOAT,
                max_temperature FLOAT,
                duration_hours INT,
                wind_speed VARCHAR(20),
                precipitation FLOAT,
                crop_damage_actual FLOAT,
                crop_damage_verified_by VARCHAR(100),
                data JSONB,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_date_type
            ON historical_events(event_date, event_type)
        """)
        
        # AI predictions table
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_predictions (
                id SERIAL PRIMARY KEY,
                prediction_id VARCHAR(100) UNIQUE NOT NULL,
                county VARCHAR(50) NOT NULL,
                event_type VARCHAR(50) NOT NULL,
                prediction_time TIMESTAMP NOT NULL,
                event_expected_time TIMESTAMP,
                probability FLOAT NOT NULL,
                expected_damage_pct FLOAT NOT NULL,
                damage_range_min FLOAT,
                damage_range_max FLOAT,
                confidence_score FLOAT NOT NULL,
                ai_model VARCHAR(100),
                reasoning TEXT,
                full_prediction JSONB NOT NULL,
                verified BOOLEAN DEFAULT FALSE,
                actual_damage_pct FLOAT,
                verification_date TIMESTAMP,
                accuracy_score FLOAT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_predictions_time
            ON ai_predictions(prediction_time DESC)
        """)
        
        # USDA reports table
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS usda_reports (
                id SERIAL PRIMARY KEY,
                report_date DATE NOT NULL,
                report_type VARCHAR(100) NOT NULL,
                state VARCHAR(10),
                production_estimate FLOAT,
                damage_estimate FLOAT,
                report_text TEXT,
                data JSONB,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        # Satellite imagery metadata
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS satellite_imagery (
                id SERIAL PRIMARY KEY,
                acquisition_date DATE NOT NULL,
                county VARCHAR(50),
                source VARCHAR(50),
                ndvi_mean FLOAT,
                ndvi_std FLOAT,
                cloud_cover_pct FLOAT,
                image_url TEXT,
                analysis_results JSONB,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        # Market prices table
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS market_prices (
                id SERIAL PRIMARY KEY,
                trade_date DATE NOT NULL UNIQUE,
                open_price FLOAT,
                high_price FLOAT,
                low_price FLOAT,
                close_price FLOAT,
                volume BIGINT,
                open_interest INT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        # Performance metrics table
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS performance_metrics (
                id SERIAL PRIMARY KEY,
                metric_date DATE NOT NULL,
                metric_type VARCHAR(100) NOT NULL,
                metric_value FLOAT NOT NULL,
                details JSONB,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_metrics_date_type
            ON performance_metrics(metric_date, metric_type)
        """)
        
        self.conn.commit()
        logger.info("All database tables created successfully")
    
    def store_weather_forecast(self, forecast: Dict) -> int:
        """Store weather forecast"""
        
        self.cursor.execute("""
            INSERT INTO weather_forecasts 
            (county, forecast_time, data, freeze_risk, max_expected_damage)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (
            forecast['county'],
            forecast['generated_at'],
            Json(forecast),
            forecast.get('freeze_risk', {}).get('risk'),
            forecast.get('freeze_risk', {}).get('max_expected_damage')
        ))
        
        forecast_id = self.cursor.fetchone()['id']
        self.conn.commit()
        
        logger.info(f"Stored forecast #{forecast_id} for {forecast['county']} County")
        return forecast_id
    
    def store_ai_prediction(self, prediction: Dict) -> int:
        """Store AI-generated prediction"""
        
        self.cursor.execute("""
            INSERT INTO ai_predictions
            (prediction_id, county, event_type, prediction_time, event_expected_time,
             probability, expected_damage_pct, damage_range_min, damage_range_max,
             confidence_score, ai_model, reasoning, full_prediction)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            prediction.get('prediction_id'),
            prediction.get('county'),
            prediction.get('event_type'),
            prediction.get('timestamp') or prediction.get('generated_at'),
            prediction.get('timing', {}).get('onset'),
            prediction.get('probability'),
            prediction.get('expected_crop_damage_pct'),
            prediction.get('damage_range', {}).get('min'),
            prediction.get('damage_range', {}).get('max'),
            prediction.get('confidence_score'),
            prediction.get('ai_model'),
            prediction.get('reasoning'),
            Json(prediction)
        ))
        
        pred_id = self.cursor.fetchone()['id']
        self.conn.commit()
        
        logger.info(f"Stored prediction #{pred_id}: {prediction.get('event_type')} - {prediction.get('expected_crop_damage_pct', 0)*100:.1f}% damage")
        return pred_id
    
    def get_historical_analogs(self, event_type: str, temperature: float = None, 
                              limit: int = 10) -> List[Dict]:
        """
        Find historical events similar to current conditions
        """
        
        query = """
            SELECT * FROM historical_events
            WHERE event_type = %s
        """
        params = [event_type]
        
        # Add temperature filter if freeze event
        if event_type == 'freeze' and temperature:
            query += " AND min_temperature BETWEEN %s AND %s"
            params.extend([temperature - 3, temperature + 3])
        
        query += " ORDER BY event_date DESC LIMIT %s"
        params.append(limit)
        
        self.cursor.execute(query, params)
        events = self.cursor.fetchall()
        
        return [dict(event) for event in events]
    
    def verify_prediction(self, prediction_id: str, actual_damage: float, 
                         verification_source: str) -> bool:
        """
        Verify a prediction against actual USDA report
        """
        
        # Get original prediction
        self.cursor.execute("""
            SELECT * FROM ai_predictions WHERE prediction_id = %s
        """, (prediction_id,))
        
        prediction = self.cursor.fetchone()
        if not prediction:
            logger.warning(f"Prediction {prediction_id} not found")
            return False
        
        # Calculate accuracy
        predicted = prediction['expected_damage_pct']
        error = abs(predicted - actual_damage)
        accuracy = 1.0 - min(error / max(predicted, actual_damage, 0.01), 1.0)
        
        # Update prediction with verification
        self.cursor.execute("""
            UPDATE ai_predictions
            SET verified = TRUE,
                actual_damage_pct = %s,
                verification_date = NOW(),
                accuracy_score = %s
            WHERE prediction_id = %s
        """, (actual_damage, accuracy, prediction_id))
        
        self.conn.commit()
        
        logger.info(f"Verified prediction {prediction_id}: {accuracy*100:.1f}% accurate")
        return True
    
    def get_prediction_performance(self, start_date: datetime = None, 
                                  end_date: datetime = None) -> Dict:
        """
        Calculate overall prediction performance metrics
        """
        
        query = """
            SELECT 
                COUNT(*) as total_predictions,
                COUNT(*) FILTER (WHERE verified = TRUE) as verified_count,
                AVG(accuracy_score) FILTER (WHERE verified = TRUE) as avg_accuracy,
                AVG(confidence_score) as avg_confidence,
                COUNT(*) FILTER (WHERE verified = TRUE AND accuracy_score >= 0.7) as accurate_predictions,
                AVG(expected_damage_pct) as avg_predicted_damage,
                AVG(actual_damage_pct) FILTER (WHERE verified = TRUE) as avg_actual_damage
            FROM ai_predictions
            WHERE 1=1
        """
        
        params = []
        if start_date:
            query += " AND prediction_time >= %s"
            params.append(start_date)
        if end_date:
            query += " AND prediction_time <= %s"
            params.append(end_date)
        
        self.cursor.execute(query, params)
        metrics = dict(self.cursor.fetchone())
        
        # Calculate additional metrics
        if metrics['verified_count'] and metrics['verified_count'] > 0:
            metrics['verification_rate'] = metrics['verified_count'] / metrics['total_predictions']
            metrics['success_rate'] = metrics['accurate_predictions'] / metrics['verified_count']
        else:
            metrics['verification_rate'] = 0
            metrics['success_rate'] = 0
        
        return metrics
    
    def store_usda_report(self, report: Dict) -> int:
        """Store USDA crop report"""
        
        self.cursor.execute("""
            INSERT INTO usda_reports
            (report_date, report_type, state, production_estimate, damage_estimate, report_text, data)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            report.get('report_date'),
            report.get('report_type'),
            report.get('state', 'FL'),
            report.get('production_estimate'),
            report.get('damage_estimate'),
            report.get('report_text'),
            Json(report)
        ))
        
        report_id = self.cursor.fetchone()['id']
        self.conn.commit()
        
        logger.info(f"Stored USDA report #{report_id}")
        return report_id
    
    def get_recent_predictions(self, days: int = 7) -> List[Dict]:
        """Get predictions from last N days"""
        
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        self.cursor.execute("""
            SELECT * FROM ai_predictions
            WHERE prediction_time >= %s
            ORDER BY prediction_time DESC
        """, (cutoff,))
        
        return [dict(row) for row in self.cursor.fetchall()]
    
    def store_market_price(self, trade_date: str, open_price: float, high: float, 
                          low: float, close: float, volume: int, 
                          open_interest: int) -> int:
        """Store daily market price data"""
        
        self.cursor.execute("""
            INSERT INTO market_prices
            (trade_date, open_price, high_price, low_price, close_price, volume, open_interest)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (trade_date) DO UPDATE
            SET open_price = EXCLUDED.open_price,
                high_price = EXCLUDED.high_price,
                low_price = EXCLUDED.low_price,
                close_price = EXCLUDED.close_price,
                volume = EXCLUDED.volume,
                open_interest = EXCLUDED.open_interest
            RETURNING id
        """, (trade_date, open_price, high, low, close, volume, open_interest))
        
        price_id = self.cursor.fetchone()['id']
        self.conn.commit()
        
        return price_id
    
    def get_price_history(self, start_date: str, end_date: str) -> List[Dict]:
        """Get historical price data"""
        
        self.cursor.execute("""
            SELECT * FROM market_prices
            WHERE trade_date BETWEEN %s AND %s
            ORDER BY trade_date ASC
        """, (start_date, end_date))
        
        return [dict(row) for row in self.cursor.fetchall()]
    
    def store_performance_metric(self, metric_type: str, value: float, 
                                details: Dict = None) -> int:
        """Store daily performance metric"""
        
        self.cursor.execute("""
            INSERT INTO performance_metrics
            (metric_date, metric_type, metric_value, details)
            VALUES (CURRENT_DATE, %s, %s, %s)
            RETURNING id
        """, (metric_type, value, Json(details) if details else None))
        
        metric_id = self.cursor.fetchone()['id']
        self.conn.commit()
        
        return metric_id
    
    def get_performance_over_time(self, metric_type: str, days: int = 30) -> List[Dict]:
        """Get performance trend over time"""
        
        cutoff = datetime.utcnow().date() - timedelta(days=days)
        
        self.cursor.execute("""
            SELECT * FROM performance_metrics
            WHERE metric_type = %s AND metric_date >= %s
            ORDER BY metric_date ASC
        """, (metric_type, cutoff))
        
        return [dict(row) for row in self.cursor.fetchall()]
    
    def seed_historical_data(self):
        """
        Seed database with historical freeze events for testing
        """
        
        historical_events = [
            {
                'event_date': '2024-01-16',
                'event_type': 'freeze',
                'county': 'Polk',
                'min_temperature': 26.0,
                'duration_hours': 5,
                'crop_damage_actual': 0.113,
                'verified_by': 'USDA February 2024 Report'
            },
            {
                'event_date': '2023-12-23',
                'event_type': 'freeze',
                'county': 'Highlands',
                'min_temperature': 28.0,
                'duration_hours': 3,
                'crop_damage_actual': 0.045,
                'verified_by': 'USDA January 2024 Report'
            },
            {
                'event_date': '2023-09-01',
                'event_type': 'hurricane',
                'county': 'Polk',
                'wind_speed': '75 mph',
                'crop_damage_actual': 0.089,
                'verified_by': 'USDA October 2023 Report'
            },
            {
                'event_date': '2024-02-08',
                'event_type': 'freeze',
                'county': 'Polk',
                'min_temperature': 24.0,
                'duration_hours': 6,
                'crop_damage_actual': 0.157,
                'verified_by': 'USDA March 2024 Report'
            }
        ]
        
        for event in historical_events:
            self.cursor.execute("""
                INSERT INTO historical_events
                (event_date, event_type, county, min_temperature, duration_hours, 
                 crop_damage_actual, crop_damage_verified_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (
                event['event_date'],
                event['event_type'],
                event.get('county'),
                event.get('min_temperature'),
                event.get('duration_hours'),
                event.get('crop_damage_actual'),
                event.get('verified_by')
            ))
        
        self.conn.commit()
        logger.info(f"Seeded {len(historical_events)} historical events")


def main():
    """Test database operations"""
    
    print("="*80)
    print("AgriQuant AI - Database Module Test")
    print("="*80)
    
    # Note: Requires PostgreSQL to be running
    # For testing, you might use SQLite instead
    
    print("\nDatabase module loaded successfully")
    print("To test, ensure PostgreSQL is running and DATABASE_URL is configured")
    print("\nExample usage:")
    print("  db = AgriQuant AIDatabase()")
    print("  db.connect()")
    print("  db.create_tables()")
    print("  db.seed_historical_data()")
    print("  db.disconnect()")


if __name__ == "__main__":
    main()
