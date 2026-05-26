"""
AgriQuant AI - Quick Demo Script
Demonstrates the complete workflow with example data
"""

import json
from datetime import datetime

# Import AgriQuant AI components
from weather_collector import NOAAWeatherCollector
from claude_engine import ClaudeAnalysisEngine
from database import AgriQuant AIDatabase


def demo_weather_collection():
    """Demo: Collect real weather data from NOAA"""
    
    print("\n" + "="*80)
    print("DEMO 1: WEATHER DATA COLLECTION")
    print("="*80)
    
    collector = NOAAWeatherCollector()
    
    print("\nFetching current weather forecast for Polk County, Florida...")
    print("(35% of Florida's orange production)")
    
    # Get comprehensive forecast
    forecast = collector.get_ensemble_forecast('Polk')
    
    if forecast:
        print("\n✓ Forecast Retrieved Successfully")
        print(f"\nForecast Office: {forecast['primary_forecast']['forecast_office']}")
        print(f"Generated: {forecast['primary_forecast']['generated_at']}")
        
        # Display freeze risk
        freeze_risk = forecast['freeze_risk']
        print(f"\nFreeze Risk: {freeze_risk['risk'].upper()}")
        
        if freeze_risk['risk'] != 'none':
            details = freeze_risk['details']
            print(f"  Temperature: {details['temperature']}°F")
            print(f"  Duration: {details['duration_hours']} hours")
            print(f"  Expected Damage: {details['expected_damage_pct']*100:.1f}%")
            print(f"  Start Time: {details['start_time']}")
        
        # Show next 12 hours of temperature
        print("\nNext 12 Hours Temperature Forecast:")
        for i, period in enumerate(forecast['primary_forecast']['hourly_forecast'][:12]):
            time_str = datetime.fromisoformat(period['time']).strftime('%H:%M')
            print(f"  {time_str}: {period['temperature']}°F - {period['short_forecast']}")
        
        # Model agreement
        agreement = forecast.get('model_agreement', {})
        print(f"\nModel Agreement: {agreement.get('agreement_score', 0)*100:.0f}%")
        print(f"  (GFS, NAM, HRRR models)")
        
        return forecast
    else:
        print("\n✗ Failed to retrieve forecast")
        return None


def demo_ai_analysis(forecast):
    """Demo: Generate AI prediction using Claude Sonnet 4"""
    
    print("\n" + "="*80)
    print("DEMO 2: AI PREDICTION GENERATION")
    print("="*80)
    
    if not forecast or forecast['freeze_risk']['risk'] == 'none':
        print("\nNo significant weather threat detected.")
        print("Creating simulated freeze scenario for demonstration...")
        
        # Create mock forecast with freeze risk
        forecast = {
            'county': 'Polk',
            'generated_at': datetime.utcnow().isoformat(),
            'freeze_risk': {
                'risk': 'severe_damage',
                'details': {
                    'severity': 'severe_damage',
                    'start_time': '2026-02-15T06:00:00Z',
                    'temperature': 24,
                    'duration_hours': 5,
                    'expected_damage_pct': 0.15,
                    'wind_speed': '5-10 mph'
                },
                'max_expected_damage': 0.15
            },
            'hourly_forecast': [
                {
                    'time': '2026-02-15T06:00:00Z',
                    'temperature': 24,
                    'wind_speed': '5 mph',
                    'short_forecast': 'Clear and very cold'
                }
            ],
            'discussion': 'Arctic air mass continues to deepen. Surface temps expected to fall into low-mid 20s.'
        }
    
    # Historical analogs (simulated)
    historical_analogs = [
        {
            'date': '2024-01-16',
            'event_type': 'freeze',
            'min_temp': 26,
            'duration_hours': 5,
            'crop_damage_actual': 0.113,
            'similarity_score': 0.87
        },
        {
            'date': '2022-01-29',
            'event_type': 'freeze',
            'min_temp': 24,
            'duration_hours': 6,
            'crop_damage_actual': 0.157,
            'similarity_score': 0.82
        }
    ]
    
    print(f"\nAnalyzing freeze event with Claude Sonnet 4...")
    print(f"Using historical analogs from similar events:")
    for analog in historical_analogs:
        print(f"  - {analog['date']}: {analog['min_temp']}°F → {analog['crop_damage_actual']*100:.1f}% damage")
    
    # Generate prediction
    engine = ClaudeAnalysisEngine()
    prediction = engine.analyze_freeze_event(forecast, historical_analogs)
    
    if prediction:
        print("\n✓ AI Prediction Generated")
        print("\n--- PREDICTION SUMMARY ---")
        print(f"Event Type: {prediction.get('event_type', 'N/A').upper()}")
        print(f"County: {prediction.get('county', 'N/A')}")
        print(f"\nProbability of Event: {prediction.get('probability', 0)*100:.0f}%")
        print(f"Expected Crop Damage: {prediction.get('expected_crop_damage_pct', 0)*100:.1f}%")
        print(f"Damage Range: {prediction.get('damage_range', {}).get('min', 0)*100:.1f}% - {prediction.get('damage_range', {}).get('max', 0)*100:.1f}%")
        print(f"\nConfidence Score: {prediction.get('confidence_score', 0)*100:.0f}%")
        print(f"Model Agreement: {prediction.get('model_agreement', 'N/A')}")
        
        # Timing
        timing = prediction.get('timing', {})
        print(f"\nExpected Timing:")
        print(f"  Onset: {timing.get('onset', 'N/A')}")
        print(f"  Duration: {timing.get('duration_hours', 'N/A')} hours")
        
        # Key factors
        print(f"\nKey Factors:")
        for factor in prediction.get('key_factors', [])[:3]:
            print(f"  • {factor}")
        
        # Uncertainties
        print(f"\nUncertainties:")
        for uncertainty in prediction.get('uncertainties', [])[:3]:
            print(f"  • {uncertainty}")
        
        print(f"\nAI Reasoning:")
        reasoning = prediction.get('reasoning', 'N/A')
        print(f"{reasoning[:400]}...")
        
        print(f"\nTokens Used: {prediction.get('tokens_used', 'N/A')}")
        print(f"AI Model: {prediction.get('ai_model', 'N/A')}")
        
        return prediction
    else:
        print("\n✗ Failed to generate prediction")
        return None


def demo_database_storage(forecast, prediction):
    """Demo: Store data in database"""
    
    print("\n" + "="*80)
    print("DEMO 3: DATABASE STORAGE")
    print("="*80)
    
    print("\nNote: This demo requires PostgreSQL to be running.")
    print("Database configuration: config.DATABASE_URL")
    print("\nTo actually run database operations:")
    print("  1. Install PostgreSQL")
    print("  2. Create database: createdb agriquant")
    print("  3. Set DATABASE_URL in .env file")
    print("  4. Run: python -c 'from database import *; db=AgriQuant AIDatabase(); db.connect(); db.create_tables()'")
    
    print("\n--- Database Schema ---")
    print("Tables that would be created:")
    print("  • weather_forecasts    - NOAA forecast data")
    print("  • ai_predictions       - Claude predictions")
    print("  • historical_events    - 40 years of verified events")
    print("  • usda_reports         - USDA crop damage reports")
    print("  • satellite_imagery    - Planet Labs / Sentinel-2 data")
    print("  • market_prices        - CME agricultural commodity futures")
    print("  • performance_metrics  - Accuracy tracking")
    
    print("\n--- Example Database Operations ---")
    print("Forecast would be stored with ID:")
    print(f"  County: {forecast.get('county', 'N/A')}")
    print(f"  Freeze Risk: {forecast.get('freeze_risk', {}).get('risk', 'N/A')}")
    
    if prediction:
        print("\nPrediction would be stored with:")
        print(f"  ID: {prediction.get('prediction_id', 'N/A')}")
        print(f"  Expected Damage: {prediction.get('expected_crop_damage_pct', 0)*100:.1f}%")
        print(f"  Confidence: {prediction.get('confidence_score', 0)*100:.0f}%")
        print(f"  Verified: False (pending USDA report)")


def demo_performance_tracking():
    """Demo: Show how performance is tracked"""
    
    print("\n" + "="*80)
    print("DEMO 4: PERFORMANCE TRACKING")
    print("="*80)
    
    print("\nAgriQuant AI tracks these metrics continuously:")
    
    print("\n--- Accuracy Metrics ---")
    print("  • Forecast Accuracy: % predictions verified by USDA")
    print("    Target: >70%")
    print("  • Mean Absolute Error: Avg difference in damage estimate")
    print("    Target: <3 percentage points")
    print("  • Confidence Calibration: 80% confident = 80% accurate")
    print("    Target: >0.90")
    
    print("\n--- Error Analysis ---")
    print("  • False Positive Rate: Predicted damage, none occurred")
    print("    Target: <20%")
    print("  • False Negative Rate: Missed significant events")
    print("    Target: <10%")
    
    print("\n--- Example Performance Report ---")
    example_metrics = {
        "period": "Last 30 days",
        "total_predictions": 23,
        "verified_count": 16,
        "avg_accuracy": 0.73,
        "success_rate": 0.70,
        "mae_pct": 2.4,
        "false_positive_rate": 0.18,
        "false_negative_rate": 0.12
    }
    
    print(json.dumps(example_metrics, indent=2))
    
    print("\n--- Event Type Breakdown ---")
    print("  Freeze events: 75% accuracy (8 events)")
    print("  Hurricane threats: 71% accuracy (7 events)")
    print("  Disease pressure: 60% accuracy (5 events)")


def demo_complete_workflow():
    """Run complete demo workflow"""
    
    print("\n" + "="*80)
    print("AgriQuant AI - COMPLETE SYSTEM DEMONSTRATION")
    print("="*80)
    print("\nThis demo shows the complete workflow:")
    print("  1. Weather data collection from NOAA")
    print("  2. AI analysis with Claude Sonnet 4")
    print("  3. Database storage")
    print("  4. Performance tracking")
    print("\nNote: Requires ANTHROPIC_API_KEY in environment")
    
    # Step 1: Weather collection
    forecast = demo_weather_collection()
    
    # Step 2: AI analysis
    prediction = demo_ai_analysis(forecast)
    
    # Step 3: Database
    if forecast and prediction:
        demo_database_storage(forecast, prediction)
    
    # Step 4: Performance
    demo_performance_tracking()
    
    # Summary
    print("\n" + "="*80)
    print("DEMO COMPLETE")
    print("="*80)
    
    print("\nNext Steps:")
    print("  1. Set up environment variables (ANTHROPIC_API_KEY, DATABASE_URL)")
    print("  2. Install PostgreSQL and create database")
    print("  3. Run full system: python main.py once")
    print("  4. Start continuous monitoring: python main.py continuous")
    print("  5. Run backtest: python backtest.py --start 2023-01-01 --end 2025-12-31")
    
    print("\nDocumentation:")
    print("  • README.md - Complete setup and usage guide")
    print("  • config.py - All system parameters and thresholds")
    print("  • Individual module files have detailed docstrings")
    
    print("\nSupport:")
    print("  • Email: research@agriquant.ai")
    print("  • GitHub: github.com/agriquant/agriquant-ai")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    import sys
    
    # Check if ANTHROPIC_API_KEY is set
    import os
    if not os.getenv('ANTHROPIC_API_KEY'):
        print("\n⚠️  WARNING: ANTHROPIC_API_KEY not set in environment")
        print("Some features will not work without Claude API access")
        print("\nTo set up:")
        print("  export ANTHROPIC_API_KEY='your-key-here'")
        print("  or add to .env file\n")
    
    # Run demo
    demo_complete_workflow()
