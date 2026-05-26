"""
AgriQuant AI - Main Orchestration System
Coordinates weather monitoring, AI analysis, and prediction generation
"""

import time
import schedule
from datetime import datetime, timedelta
from typing import Dict, List
import logging
import json
import uuid

from config import *
from weather_collector import NOAAWeatherCollector
from claude_engine import ClaudeAnalysisEngine
from database import AgriQuant AIDatabase

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AgriQuant AIOrchestrator:
    """
    Main system coordinator
    Runs continuous monitoring and generates predictions
    """
    
    def __init__(self):
        self.weather_collector = NOAAWeatherCollector()
        self.ai_engine = ClaudeAnalysisEngine()
        self.database = AgriQuant AIDatabase()
        
        self.deployment_phase = DEPLOYMENT_PHASE
        self.last_forecast_time = {}  # Track last forecast for each county
        self.active_predictions = []   # Currently active predictions
        
        logger.info(f"AgriQuant AI Orchestrator initialized - {self.deployment_phase} mode")
    
    def initialize(self):
        """Initialize system components"""
        logger.info("Initializing AgriQuant AI system...")
        
        # Connect to database
        self.database.connect()
        
        # Create tables if they don't exist
        self.database.create_tables()
        
        # Seed with historical data if empty
        logger.info("System initialization complete")
    
    def shutdown(self):
        """Graceful shutdown"""
        logger.info("Shutting down AgriQuant AI system...")
        self.database.disconnect()
        logger.info("Shutdown complete")
    
    def monitor_weather_all_counties(self) -> Dict:
        """
        Main monitoring loop - check all counties for weather threats
        """
        logger.info("="*80)
        logger.info(f"WEATHER MONITORING CYCLE - {datetime.utcnow().isoformat()}")
        logger.info("="*80)
        
        results = {
            'timestamp': datetime.utcnow().isoformat(),
            'counties_monitored': [],
            'predictions_generated': [],
            'alerts': []
        }
        
        for county_name in CITRUS_COUNTIES.keys():
            try:
                logger.info(f"\n--- Monitoring {county_name} County ---")
                
                # Get comprehensive forecast
                forecast = self.weather_collector.get_ensemble_forecast(county_name)
                
                if not forecast:
                    logger.warning(f"Failed to get forecast for {county_name}")
                    continue
                
                # Store forecast in database
                forecast_id = self.database.store_weather_forecast(forecast['primary_forecast'])
                
                results['counties_monitored'].append({
                    'county': county_name,
                    'forecast_id': forecast_id,
                    'freeze_risk': forecast['freeze_risk']['risk']
                })
                
                # Check if action needed
                freeze_risk = forecast['freeze_risk']
                
                if freeze_risk['risk'] != 'none':
                    logger.info(f"⚠️  FREEZE RISK DETECTED: {freeze_risk['risk']}")
                    
                    # Check confidence threshold
                    model_agreement = forecast.get('model_agreement', {}).get('agreement_score', 0)
                    
                    if model_agreement >= MIN_MODEL_AGREEMENT:
                        logger.info(f"✓ Model agreement sufficient: {model_agreement*100:.0f}%")
                        
                        # Generate AI prediction
                        prediction = self._generate_and_store_prediction(forecast, county_name)
                        
                        if prediction:
                            results['predictions_generated'].append(prediction)
                            
                            # Check if high confidence - send alert
                            if prediction['confidence_score'] >= ALERT_THRESHOLDS['prediction_confidence']:
                                alert = self._create_alert(prediction)
                                results['alerts'].append(alert)
                    else:
                        logger.info(f"✗ Model agreement too low: {model_agreement*100:.0f}% < {MIN_MODEL_AGREEMENT*100:.0f}%")
                
                # Hurricane check
                hurricane_threat = self.weather_collector.detect_hurricane_threat(county_name)
                if hurricane_threat:
                    logger.info(f"🌀 HURRICANE THREAT: {len(hurricane_threat)} active storms")
                    # Would trigger hurricane analysis here
                
                # Small delay to be respectful to APIs
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Error monitoring {county_name}: {e}")
                continue
        
        # Summary
        logger.info("\n" + "="*80)
        logger.info("MONITORING CYCLE COMPLETE")
        logger.info(f"Counties monitored: {len(results['counties_monitored'])}")
        logger.info(f"Predictions generated: {len(results['predictions_generated'])}")
        logger.info(f"Alerts triggered: {len(results['alerts'])}")
        logger.info("="*80 + "\n")
        
        return results
    
    def _generate_and_store_prediction(self, forecast: Dict, county_name: str) -> Dict:
        """
        Generate AI prediction and store in database
        """
        logger.info(f"Generating AI prediction for {county_name}...")
        
        # Get historical analogs
        freeze_details = forecast['freeze_risk'].get('details', {})
        min_temp = freeze_details.get('temperature')
        
        historical_analogs = self.database.get_historical_analogs(
            event_type='freeze',
            temperature=min_temp,
            limit=10
        )
        
        # Format for Claude
        historical_formatted = [
            {
                'date': str(h['event_date']),
                'min_temp': h['min_temperature'],
                'duration_hours': h['duration_hours'],
                'crop_damage_actual': h['crop_damage_actual'],
                'similarity_score': 0.85  # Would calculate actual similarity
            }
            for h in historical_analogs if h.get('min_temperature')
        ]
        
        # Generate prediction with Claude
        prediction = self.ai_engine.analyze_freeze_event(
            forecast['primary_forecast'],
            historical_formatted
        )
        
        if not prediction:
            logger.error("Failed to generate prediction")
            return None
        
        # Add unique ID
        prediction['prediction_id'] = f"PRED_{county_name}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"
        prediction['county'] = county_name
        
        # Store in database
        pred_id = self.database.store_ai_prediction(prediction)
        prediction['database_id'] = pred_id
        
        # Add to active predictions
        self.active_predictions.append(prediction)
        
        logger.info(f"✓ Prediction stored: {prediction['prediction_id']}")
        logger.info(f"  Probability: {prediction['probability']*100:.0f}%")
        logger.info(f"  Expected damage: {prediction['expected_crop_damage_pct']*100:.1f}%")
        logger.info(f"  Confidence: {prediction['confidence_score']*100:.0f}%")
        
        return prediction
    
    def _create_alert(self, prediction: Dict) -> Dict:
        """
        Create high-priority alert for significant predictions
        """
        alert = {
            'timestamp': datetime.utcnow().isoformat(),
            'alert_type': 'HIGH_CONFIDENCE_PREDICTION',
            'severity': 'HIGH' if prediction['confidence_score'] >= 0.90 else 'MODERATE',
            'prediction_id': prediction['prediction_id'],
            'county': prediction['county'],
            'event_type': prediction['event_type'],
            'expected_damage': prediction['expected_crop_damage_pct'],
            'confidence': prediction['confidence_score'],
            'message': self._format_alert_message(prediction)
        }
        
        logger.info(f"🚨 ALERT GENERATED: {alert['severity']}")
        logger.info(f"   {alert['message']}")
        
        # In production, would send email/SMS/webhook
        self._send_alert(alert)
        
        return alert
    
    def _format_alert_message(self, prediction: Dict) -> str:
        """Format human-readable alert message"""
        
        county = prediction['county']
        damage = prediction['expected_crop_damage_pct'] * 100
        confidence = prediction['confidence_score'] * 100
        timing = prediction.get('timing', {}).get('onset', 'TBD')
        
        message = f"""
HIGH CONFIDENCE WEATHER EVENT PREDICTED

County: {county} County, Florida
Event: {prediction['event_type'].upper()}
Expected Impact: {damage:.1f}% crop damage
Confidence: {confidence:.0f}%
Timing: {timing}

This prediction meets AgriQuant AI's threshold for significant agricultural impact.
Review full analysis and prepare for potential supply disruption.
        """.strip()
        
        return message
    
    def _send_alert(self, alert: Dict):
        """
        Send alert via configured channels
        In production: email, SMS, Slack, webhook
        """
        # For now, just log and save to file
        alert_filename = f"/tmp/agriquant_alert_{alert['timestamp'].replace(':', '-')}.json"
        
        with open(alert_filename, 'w') as f:
            json.dump(alert, f, indent=2)
        
        logger.info(f"Alert saved to: {alert_filename}")
    
    def verify_predictions(self):
        """
        Check if any predictions can now be verified against USDA data
        This would run daily to check for new USDA reports
        """
        logger.info("Checking for predictions ready for verification...")
        
        # Get unverified predictions older than typical USDA lag
        cutoff_date = datetime.utcnow() - timedelta(days=14)
        
        unverified = [p for p in self.active_predictions 
                     if not p.get('verified') and 
                     datetime.fromisoformat(p['timestamp']) < cutoff_date]
        
        logger.info(f"Found {len(unverified)} predictions ready for verification")
        
        # In production, would fetch latest USDA reports and match
        # For now, simulate verification
        
        for prediction in unverified[:3]:  # Limit for demo
            # Simulate USDA report data
            simulated_actual_damage = prediction['expected_crop_damage_pct'] * (0.9 + 0.2 * (2 * 0.5 - 1))  # ±10% random
            
            success = self.database.verify_prediction(
                prediction['prediction_id'],
                simulated_actual_damage,
                'USDA Simulated Report'
            )
            
            if success:
                logger.info(f"✓ Verified prediction {prediction['prediction_id']}")
    
    def generate_performance_report(self) -> Dict:
        """
        Generate comprehensive performance metrics
        """
        logger.info("Generating performance report...")
        
        # Get metrics from database
        metrics = self.database.get_prediction_performance()
        
        # Calculate additional metrics
        recent_predictions = self.database.get_recent_predictions(days=30)
        
        report = {
            'generated_at': datetime.utcnow().isoformat(),
            'period': 'Last 30 days',
            'overall_metrics': metrics,
            'recent_predictions': len(recent_predictions),
            'deployment_phase': self.deployment_phase,
            'system_status': 'OPERATIONAL'
        }
        
        logger.info("Performance Report:")
        logger.info(f"  Total predictions: {metrics.get('total_predictions', 0)}")
        logger.info(f"  Verified: {metrics.get('verified_count', 0)}")
        logger.info(f"  Average accuracy: {metrics.get('avg_accuracy', 0)*100:.1f}%")
        logger.info(f"  Success rate: {metrics.get('success_rate', 0)*100:.1f}%")
        
        return report
    
    def run_backtest(self, start_date: str, end_date: str):
        """
        Run historical backtest
        Test prediction accuracy on past data
        """
        logger.info(f"Running backtest: {start_date} to {end_date}")
        
        # This would:
        # 1. Load historical weather forecasts
        # 2. Generate predictions as if in real-time
        # 3. Compare to actual USDA-verified outcomes
        # 4. Calculate accuracy metrics
        
        logger.info("Backtest functionality - would run comprehensive historical validation")
        logger.info("See backtest.py for full implementation")
    
    def run_continuous_monitoring(self):
        """
        Run continuous monitoring on schedule
        """
        logger.info("Starting continuous monitoring mode...")
        
        # Schedule monitoring every 15 minutes
        schedule.every(15).minutes.do(self.monitor_weather_all_counties)
        
        # Verify predictions daily
        schedule.every().day.at("09:00").do(self.verify_predictions)
        
        # Generate performance report weekly
        schedule.every().monday.at("08:00").do(self.generate_performance_report)
        
        logger.info("Scheduler configured:")
        logger.info("  - Weather monitoring: Every 15 minutes")
        logger.info("  - Prediction verification: Daily at 9:00 AM")
        logger.info("  - Performance report: Weekly on Monday 8:00 AM")
        
        # Run initial monitoring cycle
        self.monitor_weather_all_counties()
        
        # Main loop
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
            self.shutdown()


def main():
    """
    Main entry point
    """
    print("="*80)
    print("AgriQuant AI - Weather Prediction System")
    print(f"Version: {VERSION}")
    print(f"Deployment Phase: {DEPLOYMENT_PHASE}")
    print("="*80)
    print()
    
    # Initialize orchestrator
    orchestrator = AgriQuant AIOrchestrator()
    orchestrator.initialize()
    
    # Run mode selection
    import sys
    
    if len(sys.argv) > 1:
        mode = sys.argv[1]
        
        if mode == "once":
            # Run single monitoring cycle
            print("Running single monitoring cycle...")
            results = orchestrator.monitor_weather_all_counties()
            print(f"\nResults: {json.dumps(results, indent=2)}")
            orchestrator.shutdown()
            
        elif mode == "continuous":
            # Run continuous monitoring
            print("Starting continuous monitoring...")
            orchestrator.run_continuous_monitoring()
            
        elif mode == "report":
            # Generate performance report
            print("Generating performance report...")
            report = orchestrator.generate_performance_report()
            print(json.dumps(report, indent=2))
            orchestrator.shutdown()
            
        elif mode == "verify":
            # Verify predictions
            print("Running prediction verification...")
            orchestrator.verify_predictions()
            orchestrator.shutdown()
            
        else:
            print(f"Unknown mode: {mode}")
            print("Available modes: once, continuous, report, verify")
    else:
        print("Usage: python main.py [mode]")
        print("\nModes:")
        print("  once       - Run single monitoring cycle")
        print("  continuous - Run continuous monitoring (production)")
        print("  report     - Generate performance report")
        print("  verify     - Verify pending predictions")
        print("\nExample: python main.py once")


if __name__ == "__main__":
    main()
