"""
AgriQuant AI - Backtesting Module
Validates prediction accuracy on historical weather and crop data
"""

import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import logging
import json
import numpy as np

from config import *
from database import AgriQuant AIDatabase
from claude_engine import ClaudeAnalysisEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AgriQuant AIBacktest:
    """
    Historical validation of prediction accuracy
    """
    
    def __init__(self, start_date: str, end_date: str):
        self.start_date = datetime.strptime(start_date, '%Y-%m-%d')
        self.end_date = datetime.strptime(end_date, '%Y-%m-%d')
        self.database = AgriQuant AIDatabase()
        self.ai_engine = ClaudeAnalysisEngine()
        
        self.results = {
            'total_events': 0,
            'predictions_generated': 0,
            'predictions_verified': 0,
            'correct_predictions': 0,
            'false_positives': 0,
            'false_negatives': 0,
            'accuracy_scores': [],
            'confidence_scores': [],
            'event_results': []
        }
        
        logger.info(f"Backtest initialized: {start_date} to {end_date}")
    
    def load_historical_events(self) -> List[Dict]:
        """
        Load all historical freeze/hurricane events in date range
        """
        self.database.connect()
        
        query = """
            SELECT * FROM historical_events
            WHERE event_date BETWEEN %s AND %s
            ORDER BY event_date ASC
        """
        
        self.database.cursor.execute(query, (self.start_date, self.end_date))
        events = [dict(row) for row in self.database.cursor.fetchall()]
        
        logger.info(f"Loaded {len(events)} historical events")
        return events
    
    def simulate_forecast(self, event: Dict, days_before: int = 3) -> Dict:
        """
        Simulate what the forecast would have looked like N days before event
        
        In production, would use archived NOAA forecasts
        For backtest, we reconstruct based on event data
        """
        event_date = event['event_date']
        forecast_date = event_date - timedelta(days=days_before)
        
        # Reconstruct forecast based on what actually happened
        simulated_forecast = {
            'county': event.get('county', 'Polk'),
            'generated_at': forecast_date.isoformat(),
            'freeze_risk': {
                'risk': 'none',
                'details': {},
                'max_expected_damage': 0
            },
            'hourly_forecast': [],
            'discussion': f"Simulated forecast for {event_date}"
        }
        
        # If freeze event, simulate freeze forecast
        if event['event_type'] == 'freeze':
            min_temp = event.get('min_temperature')
            duration = event.get('duration_hours', 4)
            
            if min_temp:
                # Determine severity
                severity = 'none'
                for sev, threshold in FREEZE_THRESHOLDS.items():
                    if min_temp <= threshold['temp'] and duration >= threshold['duration_hours']:
                        severity = sev
                        break
                
                if severity != 'none':
                    simulated_forecast['freeze_risk'] = {
                        'risk': severity,
                        'details': {
                            'severity': severity,
                            'start_time': (forecast_date + timedelta(days=days_before)).isoformat(),
                            'temperature': min_temp,
                            'duration_hours': duration,
                            'expected_damage_pct': FREEZE_THRESHOLDS[severity]['damage_pct'],
                            'wind_speed': event.get('wind_speed', '5-10 mph')
                        },
                        'max_expected_damage': FREEZE_THRESHOLDS[severity]['damage_pct']
                    }
                    
                    # Simulate hourly forecast showing temperature drop
                    for hour in range(72):
                        temp = 32 - (hour / 72) * (32 - min_temp)  # Linear drop
                        simulated_forecast['hourly_forecast'].append({
                            'time': (forecast_date + timedelta(hours=hour)).isoformat(),
                            'temperature': temp,
                            'wind_speed': '5 mph',
                            'short_forecast': 'Cold and clear'
                        })
        
        return simulated_forecast
    
    def generate_prediction(self, forecast: Dict, event: Dict) -> Dict:
        """
        Generate AI prediction based on simulated forecast
        """
        # Get historical analogs (events before this date)
        event_date = event['event_date']
        min_temp = event.get('min_temperature')
        
        # Query events before this date for analogs
        if min_temp:
            query = """
                SELECT * FROM historical_events
                WHERE event_type = 'freeze'
                AND event_date < %s
                AND min_temperature BETWEEN %s AND %s
                ORDER BY event_date DESC
                LIMIT 10
            """
            self.database.cursor.execute(query, (event_date, min_temp - 3, min_temp + 3))
            analogs = [dict(row) for row in self.database.cursor.fetchall()]
            
            # Format for Claude
            historical_formatted = [
                {
                    'date': str(h['event_date']),
                    'min_temp': h['min_temperature'],
                    'duration_hours': h['duration_hours'],
                    'crop_damage_actual': h['crop_damage_actual'],
                    'similarity_score': 0.85
                }
                for h in analogs
            ]
        else:
            historical_formatted = []
        
        # Generate prediction with Claude
        prediction = self.ai_engine.analyze_freeze_event(forecast, historical_formatted)
        
        return prediction
    
    def evaluate_prediction(self, prediction: Dict, actual_event: Dict) -> Dict:
        """
        Compare prediction to actual outcome
        """
        actual_damage = actual_event.get('crop_damage_actual', 0)
        predicted_damage = prediction.get('expected_crop_damage_pct', 0)
        
        # Calculate error
        absolute_error = abs(predicted_damage - actual_damage)
        relative_error = absolute_error / max(actual_damage, 0.01)  # Avoid division by zero
        
        # Accuracy score (1.0 = perfect, 0.0 = completely wrong)
        accuracy = 1.0 - min(relative_error, 1.0)
        
        # Check if directionally correct (predicted damage vs. no damage)
        damage_threshold = 0.03  # 3% is considered significant damage
        predicted_damage_occurred = predicted_damage >= damage_threshold
        actual_damage_occurred = actual_damage >= damage_threshold
        directionally_correct = predicted_damage_occurred == actual_damage_occurred
        
        # Determine if prediction was "successful" (within reasonable margin)
        margin_of_error = 0.05  # 5 percentage points
        successful = absolute_error <= margin_of_error
        
        result = {
            'prediction_id': prediction.get('prediction_id'),
            'event_date': str(actual_event['event_date']),
            'county': actual_event['county'],
            'event_type': actual_event['event_type'],
            'predicted_damage': predicted_damage,
            'actual_damage': actual_damage,
            'absolute_error': absolute_error,
            'relative_error': relative_error,
            'accuracy_score': accuracy,
            'confidence_score': prediction.get('confidence_score', 0),
            'directionally_correct': directionally_correct,
            'successful': successful,
            'false_positive': predicted_damage_occurred and not actual_damage_occurred,
            'false_negative': not predicted_damage_occurred and actual_damage_occurred
        }
        
        return result
    
    def run_backtest(self) -> Dict:
        """
        Execute full backtest
        """
        logger.info("="*80)
        logger.info(f"RUNNING BACKTEST: {self.start_date.date()} to {self.end_date.date()}")
        logger.info("="*80)
        
        # Load historical events
        events = self.load_historical_events()
        self.results['total_events'] = len(events)
        
        if not events:
            logger.warning("No historical events found in date range")
            return self.results
        
        # Process each event
        for i, event in enumerate(events, 1):
            logger.info(f"\n[{i}/{len(events)}] Processing event: {event['event_date']} - {event['event_type']}")
            
            try:
                # Simulate forecast 3 days before event
                forecast = self.simulate_forecast(event, days_before=3)
                
                # Check if forecast would have triggered prediction
                freeze_risk = forecast['freeze_risk']['risk']
                
                if freeze_risk == 'none':
                    logger.info("  No freeze risk detected in forecast - skipping")
                    continue
                
                logger.info(f"  Freeze risk detected: {freeze_risk}")
                
                # Generate prediction
                prediction = self.generate_prediction(forecast, event)
                
                if not prediction:
                    logger.warning("  Failed to generate prediction")
                    continue
                
                self.results['predictions_generated'] += 1
                
                logger.info(f"  Predicted damage: {prediction['expected_crop_damage_pct']*100:.1f}%")
                logger.info(f"  Confidence: {prediction['confidence_score']*100:.0f}%")
                
                # Evaluate against actual outcome
                if event.get('crop_damage_actual') is not None:
                    evaluation = self.evaluate_prediction(prediction, event)
                    
                    logger.info(f"  Actual damage: {event['crop_damage_actual']*100:.1f}%")
                    logger.info(f"  Accuracy: {evaluation['accuracy_score']*100:.0f}%")
                    logger.info(f"  Successful: {'✓' if evaluation['successful'] else '✗'}")
                    
                    # Update results
                    self.results['predictions_verified'] += 1
                    self.results['accuracy_scores'].append(evaluation['accuracy_score'])
                    self.results['confidence_scores'].append(evaluation['confidence_score'])
                    self.results['event_results'].append(evaluation)
                    
                    if evaluation['successful']:
                        self.results['correct_predictions'] += 1
                    
                    if evaluation['false_positive']:
                        self.results['false_positives'] += 1
                    
                    if evaluation['false_negative']:
                        self.results['false_negatives'] += 1
                
            except Exception as e:
                logger.error(f"  Error processing event: {e}")
                continue
        
        # Calculate summary statistics
        self._calculate_summary_statistics()
        
        # Display results
        self._display_results()
        
        return self.results
    
    def _calculate_summary_statistics(self):
        """Calculate aggregate metrics"""
        
        if self.results['accuracy_scores']:
            self.results['mean_accuracy'] = np.mean(self.results['accuracy_scores'])
            self.results['median_accuracy'] = np.median(self.results['accuracy_scores'])
            self.results['std_accuracy'] = np.std(self.results['accuracy_scores'])
        
        if self.results['predictions_verified'] > 0:
            self.results['success_rate'] = (self.results['correct_predictions'] / 
                                           self.results['predictions_verified'])
            self.results['false_positive_rate'] = (self.results['false_positives'] / 
                                                   self.results['predictions_verified'])
            self.results['false_negative_rate'] = (self.results['false_negatives'] / 
                                                   self.results['predictions_verified'])
        
        # Calculate Mean Absolute Error
        if self.results['event_results']:
            errors = [r['absolute_error'] for r in self.results['event_results']]
            self.results['mae'] = np.mean(errors)
            self.results['mae_pct'] = self.results['mae'] * 100  # Convert to percentage points
        
        # Confidence calibration
        # Are 80% confident predictions actually correct 80% of time?
        if self.results['event_results']:
            self._calculate_confidence_calibration()
    
    def _calculate_confidence_calibration(self):
        """
        Check if confidence scores are well-calibrated
        E.g., if AI says 80% confident, are 80% of those predictions accurate?
        """
        bins = [0, 0.6, 0.7, 0.8, 0.9, 1.0]
        bin_labels = ['60-70%', '70-80%', '80-90%', '90-100%']
        
        calibration = {}
        
        for i in range(len(bins)-1):
            lower, upper = bins[i], bins[i+1]
            bin_predictions = [r for r in self.results['event_results'] 
                             if lower <= r['confidence_score'] < upper]
            
            if bin_predictions:
                bin_accuracy = np.mean([r['accuracy_score'] for r in bin_predictions])
                bin_success = sum(1 for r in bin_predictions if r['successful'])
                
                calibration[bin_labels[i]] = {
                    'count': len(bin_predictions),
                    'mean_confidence': np.mean([r['confidence_score'] for r in bin_predictions]),
                    'mean_accuracy': bin_accuracy,
                    'success_rate': bin_success / len(bin_predictions)
                }
        
        self.results['confidence_calibration'] = calibration
    
    def _display_results(self):
        """Display backtest results"""
        
        logger.info("\n" + "="*80)
        logger.info("BACKTEST RESULTS")
        logger.info("="*80)
        
        logger.info(f"\nDate Range: {self.start_date.date()} to {self.end_date.date()}")
        logger.info(f"Total Events: {self.results['total_events']}")
        logger.info(f"Predictions Generated: {self.results['predictions_generated']}")
        logger.info(f"Predictions Verified: {self.results['predictions_verified']}")
        
        logger.info("\n--- ACCURACY METRICS ---")
        logger.info(f"Mean Accuracy: {self.results.get('mean_accuracy', 0)*100:.1f}%")
        logger.info(f"Median Accuracy: {self.results.get('median_accuracy', 0)*100:.1f}%")
        logger.info(f"Success Rate (±5pp): {self.results.get('success_rate', 0)*100:.1f}%")
        logger.info(f"Mean Absolute Error: {self.results.get('mae_pct', 0):.2f} percentage points")
        
        logger.info("\n--- ERROR ANALYSIS ---")
        logger.info(f"Correct Predictions: {self.results['correct_predictions']}")
        logger.info(f"False Positives: {self.results['false_positives']}")
        logger.info(f"False Negatives: {self.results['false_negatives']}")
        logger.info(f"FP Rate: {self.results.get('false_positive_rate', 0)*100:.1f}%")
        logger.info(f"FN Rate: {self.results.get('false_negative_rate', 0)*100:.1f}%")
        
        if self.results.get('confidence_calibration'):
            logger.info("\n--- CONFIDENCE CALIBRATION ---")
            for bin_label, stats in self.results['confidence_calibration'].items():
                logger.info(f"{bin_label} confidence:")
                logger.info(f"  Count: {stats['count']}")
                logger.info(f"  Mean Confidence: {stats['mean_confidence']*100:.0f}%")
                logger.info(f"  Mean Accuracy: {stats['mean_accuracy']*100:.0f}%")
                logger.info(f"  Success Rate: {stats['success_rate']*100:.0f}%")
        
        # Event type breakdown
        logger.info("\n--- EVENT TYPE BREAKDOWN ---")
        event_types = {}
        for result in self.results['event_results']:
            event_type = result['event_type']
            if event_type not in event_types:
                event_types[event_type] = []
            event_types[event_type].append(result)
        
        for event_type, results in event_types.items():
            accuracy = np.mean([r['accuracy_score'] for r in results])
            success = sum(1 for r in results if r['successful'])
            logger.info(f"{event_type.upper()}: {accuracy*100:.0f}% accuracy ({success}/{len(results)} successful)")
    
    def save_results(self, filename: str):
        """Save backtest results to JSON file"""
        
        # Convert numpy types to native Python for JSON serialization
        results_json = json.loads(json.dumps(self.results, default=str))
        
        with open(filename, 'w') as f:
            json.dump(results_json, f, indent=2)
        
        logger.info(f"\nResults saved to: {filename}")


def main():
    """Run backtest from command line"""
    
    parser = argparse.ArgumentParser(description='AgriQuant AI Backtest')
    parser.add_argument('--start', required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('--output', default='backtest_results.json', help='Output file')
    
    args = parser.parse_args()
    
    print("="*80)
    print("AgriQuant AI - Historical Backtest")
    print("="*80)
    print(f"Testing period: {args.start} to {args.end}")
    print("="*80)
    
    # Run backtest
    backtest = AgriQuant AIBacktest(args.start, args.end)
    results = backtest.run_backtest()
    
    # Save results
    backtest.save_results(args.output)
    
    print("\n" + "="*80)
    print("Backtest complete!")
    print("="*80)


if __name__ == "__main__":
    main()
