"""
AgriQuant AI - Claude Sonnet 4 Analysis Engine
Uses Claude AI to analyze weather forecasts and generate crop damage predictions
"""

import anthropic
import json
from datetime import datetime
from typing import Dict, List, Optional
import logging
from config import *

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ClaudeAnalysisEngine:
    """
    Uses Claude Sonnet 4 to analyze weather data and generate predictions
    """
    
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self.model = CLAUDE_MODEL
        self.system_prompt = SYSTEM_PROMPT
    
    def analyze_weather_event(self, commodity: str, region: str,
                           event_type: str, forecast_data: dict,
                           historical_analogs: list) -> dict:
        """
        Generalized weather event analysis for any commodity/region.
        Wraps commodity-specific methods (analyze_freeze_event,
        analyze_hurricane_threat, etc.) with a unified interface.
        Added Q1 2026 as part of multi-commodity expansion.
        """
        if commodity == 'OJ' and event_type == 'freeze':
            return self.analyze_freeze_event(forecast_data, historical_analogs)
        elif commodity == 'OJ' and event_type == 'hurricane':
            return self.analyze_hurricane_threat(forecast_data)
        elif commodity == 'KC':
            from coffee_brazil_collector import CoffeeBrazilCollector
            return {'commodity': 'KC', 'region': region,
                    'event_type': event_type, 'forecast': forecast_data}
        elif commodity == 'CC':
            from cocoa_westafrica_collector import CocoaWestAfricaCollector
            return {'commodity': 'CC', 'region': region,
                    'event_type': event_type, 'forecast': forecast_data}
        else:
            return {'commodity': commodity, 'region': region,
                    'event_type': event_type, 'status': 'analysis_pending'}

    def analyze_freeze_event(self, forecast_data: Dict, historical_analogs: List[Dict]) -> Dict:
        """
        Analyze freeze forecast and generate crop damage prediction
        
        Args:
            forecast_data: Weather forecast from NOAA
            historical_analogs: Similar historical freeze events
            
        Returns:
            Dict with prediction, confidence, and reasoning
        """
        
        # Construct detailed analysis prompt
        prompt = f"""Analyze this freeze forecast for Florida's agricultural crop and generate a precise crop damage prediction.

CURRENT FORECAST DATA:
County: {forecast_data['county']}
Generated: {forecast_data['generated_at']}

FREEZE RISK DETECTED:
{json.dumps(forecast_data.get('freeze_risk', {}), indent=2)}

HOURLY TEMPERATURE FORECAST (Next 72 hours):
"""
        
        # Add key hourly data points
        for i, period in enumerate(forecast_data['hourly_forecast'][:24]):
            prompt += f"\n{period['time']}: {period['temperature']}°F, Wind: {period['wind_speed']}, {period['short_forecast']}"
        
        prompt += f"\n\nMETEOROLOGIST DISCUSSION:\n{forecast_data.get('discussion', 'N/A')[:1000]}"
        
        # Add historical precedents
        if historical_analogs:
            prompt += f"\n\nHISTORICAL PRECEDENTS (Similar Events):\n"
            for analog in historical_analogs:
                prompt += f"\n- {analog['date']}: {analog['min_temp']}°F for {analog['duration_hours']}hrs → {analog['crop_damage_actual']*100:.1f}% crop loss (verified)"
        
        # Add current grove conditions
        current_month = datetime.now().month
        seasonal_vulnerability = SEASONAL_VULNERABILITY.get(current_month, 0.5)
        
        prompt += f"""

CURRENT GROVE CONDITIONS:
- Month: {datetime.now().strftime('%B')} (Seasonal vulnerability: {seasonal_vulnerability*100:.0f}%)
- Drought stress: Assume moderate (10% increased vulnerability)
- Tree age: Mixed (5-25 years)

ACADEMIC MODELS TO APPLY:
1. Singerman et al. (2018) freeze damage regression:
   - Base damage: {SINGERMAN_FREEZE_MODEL['base_damage']*100}%
   - Temperature coefficient: {SINGERMAN_FREEZE_MODEL['temp_coefficient']} per °F below 32°F
   - Duration coefficient: {SINGERMAN_FREEZE_MODEL['duration_coefficient']} per hour
   
2. Spatial propagation:
   - {forecast_data['county']} County produces {CITRUS_COUNTIES[forecast_data['county']]['production_share']*100}% of Florida crop

YOUR TASK:
Generate a comprehensive freeze impact prediction with:

1. PROBABILITY ASSESSMENT
   - Probability of damaging freeze occurring: X%
   - Confidence in forecast: [High/Moderate/Low]
   - Key uncertainty factors

2. CROP DAMAGE ESTIMATE
   - Expected crop loss percentage: X.X%
   - Range: [minimum - maximum]
   - Calculation methodology

3. SPATIAL IMPACT
   - Which counties will be affected
   - Total Florida production impact

4. TIMING
   - When will freeze occur (48-72 hour window)
   - Duration of freeze event
   - Recovery timeline

5. HISTORICAL COMPARISON
   - Which historical events is this most similar to?
   - How does this compare in severity?

6. CONFIDENCE SCORE
   - Overall prediction confidence: 0-100%
   - What could change this prediction?

7. REASONING
   - Step-by-step analysis
   - Key factors driving prediction
   - Risks and limitations

Respond ONLY in valid JSON format with this structure:
{{
  "prediction_id": "unique_id",
  "timestamp": "ISO8601",
  "event_type": "freeze",
  "county": "name",
  "probability": 0.XX,
  "expected_crop_damage_pct": 0.XX,
  "damage_range": {{"min": 0.XX, "max": 0.XX}},
  "confidence_score": 0.XX,
  "timing": {{"onset": "ISO8601", "duration_hours": X}},
  "spatial_impact": {{"affected_counties": [], "total_fl_production_affected_pct": 0.XX}},
  "historical_comparison": "text",
  "reasoning": "detailed step-by-step analysis",
  "key_factors": ["factor1", "factor2"],
  "uncertainties": ["uncertainty1", "uncertainty2"],
  "model_agreement": "high/moderate/low",
  "usda_confirmation_expected": "date"
}}
"""
        
        # Call Claude Sonnet 4
        try:
            logger.info(f"Sending freeze analysis request to Claude Sonnet 4...")
            
            message = self.client.messages.create(
                model=self.model,
                max_tokens=CLAUDE_SETTINGS['max_tokens'],
                temperature=CLAUDE_SETTINGS['temperature'],
                system=self.system_prompt,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            # Extract response
            response_text = message.content[0].text
            
            # Parse JSON response
            # Remove any markdown code fences if present
            if response_text.startswith('```'):
                response_text = response_text.split('```')[1]
                if response_text.startswith('json'):
                    response_text = response_text[4:]
            
            prediction = json.loads(response_text.strip())
            
            # Add metadata
            prediction['ai_model'] = self.model
            prediction['ai_model_version'] = CLAUDE_MODEL
            prediction['tokens_used'] = message.usage.input_tokens + message.usage.output_tokens
            prediction['generated_at'] = datetime.utcnow().isoformat()
            
            logger.info(f"✓ Prediction generated successfully")
            logger.info(f"  Probability: {prediction['probability']*100:.0f}%")
            logger.info(f"  Expected damage: {prediction['expected_crop_damage_pct']*100:.1f}%")
            logger.info(f"  Confidence: {prediction['confidence_score']*100:.0f}%")
            
            return prediction
            
        except anthropic.APIError as e:
            logger.error(f"Claude API error: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response as JSON: {e}")
            logger.error(f"Response was: {response_text}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in analyze_freeze_event: {e}")
            return None
    
    def analyze_hurricane_threat(self, forecast_data: Dict, hurricane_data: Dict) -> Dict:
        """
        Analyze hurricane threat and predict crop impact
        """
        
        prompt = f"""Analyze this hurricane threat to Florida's agricultural crop.

HURRICANE DATA:
{json.dumps(hurricane_data, indent=2)}

COUNTY FORECAST:
County: {forecast_data['county']}
Current conditions: {forecast_data['hourly_forecast'][0]['short_forecast']}

HISTORICAL HURRICANE IMPACTS:
- 2017 Hurricane Irma: Cat 4, 130mph → 10% crop loss in central FL
- 2004 Hurricane Charley: Cat 4, direct hit Polk County → 18% crop loss
- 2023 Hurricane Idalia: Near miss → 2% crop loss (mostly wind damage)

YOUR TASK:
Assess hurricane threat and predict crop damage.

Consider:
1. Forecast cone probability (50% cone, 90% cone)
2. Current intensity and predicted intensity at landfall
3. Wind damage to fruit (50mph+ causes fruit drop)
4. Rainfall flooding risk (8+ inches causes root damage)
5. Storm surge (not major factor for inland citrus)
6. Timing (is fruit on trees?)

Respond in JSON with same structure as freeze analysis, adapted for hurricane scenario.
Include both direct hit scenario and miss scenario with probabilities.
"""
        
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=CLAUDE_SETTINGS['max_tokens'],
                temperature=CLAUDE_SETTINGS['temperature'],
                system=self.system_prompt,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = message.content[0].text
            if response_text.startswith('```'):
                response_text = response_text.split('```')[1]
                if response_text.startswith('json'):
                    response_text = response_text[4:]
            
            prediction = json.loads(response_text.strip())
            prediction['ai_model'] = self.model
            prediction['tokens_used'] = message.usage.input_tokens + message.usage.output_tokens
            prediction['generated_at'] = datetime.utcnow().isoformat()
            
            return prediction
            
        except Exception as e:
            logger.error(f"Error in analyze_hurricane_threat: {e}")
            return None
    
    def analyze_disease_pressure(self, forecast_data: Dict, weather_pattern: Dict) -> Dict:
        """
        Analyze weather patterns for crop disease disease pressure
        
        Based on Li et al. (2020) research on psyllid population dynamics
        """
        
        prompt = f"""Analyze weather conditions for crop disease disease pressure.

WEATHER PATTERN (Last 14 days + Forecast):
{json.dumps(weather_pattern, indent=2)}

DISEASE BIOLOGY (Asian Citrus Psyllid):
- Optimal temperature: 85-95°F
- Requires humidity >70%
- Reproduces rapidly in warm/wet conditions
- Each generation: 14-21 days
- Transmits HLB (crop disease) bacteria

Li et al. (2020) RESEARCH FINDINGS:
- 10+ consecutive days of optimal conditions → 18-24% psyllid population increase
- Population increase correlates with disease transmission
- 6-8% additional crop loss materializes over 6-12 months
- USDA confirmation typically 7-10 days after weather pattern

CURRENT GROVE STATUS:
- 90% of Florida groves already infected with HLB
- Disease compounds other stresses (freeze, drought)

YOUR TASK:
Predict disease pressure increase and crop impact.

Respond in JSON with:
- Probability of population increase
- Expected crop damage (6-12 month timeline)
- When USDA will confirm increased disease pressure
- Confidence score
"""
        
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=CLAUDE_SETTINGS['max_tokens'],
                temperature=CLAUDE_SETTINGS['temperature'],
                system=self.system_prompt,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = message.content[0].text
            if response_text.startswith('```'):
                response_text = response_text.split('```')[1]
                if response_text.startswith('json'):
                    response_text = response_text[4:]
            
            prediction = json.loads(response_text.strip())
            prediction['ai_model'] = self.model
            prediction['tokens_used'] = message.usage.input_tokens + message.usage.output_tokens
            prediction['generated_at'] = datetime.utcnow().isoformat()
            
            return prediction
            
        except Exception as e:
            logger.error(f"Error in analyze_disease_pressure: {e}")
            return None
    
    def validate_prediction_quality(self, prediction: Dict) -> Dict:
        """
        Meta-analysis: Have Claude validate its own prediction quality
        """
        
        prompt = f"""Review this prediction for quality and identify potential issues.

PREDICTION TO REVIEW:
{json.dumps(prediction, indent=2)}

YOUR TASK:
Critically evaluate this prediction:

1. DATA QUALITY
   - Is forecast data sufficient?
   - Are historical analogs relevant?
   - What data is missing?

2. REASONING QUALITY
   - Is the logic sound?
   - Are academic models applied correctly?
   - Are there logical gaps?

3. CONFIDENCE CALIBRATION
   - Is confidence score justified?
   - What could make this prediction wrong?
   - Are uncertainties properly acknowledged?

4. ACTIONABILITY
   - Is this prediction specific enough?
   - Can it be validated against USDA reports?
   - Clear timeline for verification?

Respond in JSON:
{{
  "quality_score": 0.XX,
  "strengths": ["strength1", "strength2"],
  "weaknesses": ["weakness1", "weakness2"],
  "missing_data": ["data1", "data2"],
  "recommended_confidence_adjustment": "increase/decrease/maintain",
  "verification_plan": "how to validate this prediction",
  "overall_assessment": "text"
}}
"""
        
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                temperature=0.3,  # Slightly higher for critical analysis
                system="You are a critical reviewer of AI predictions. Your job is to identify flaws and improve prediction quality.",
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = message.content[0].text
            if response_text.startswith('```'):
                response_text = response_text.split('```')[1]
                if response_text.startswith('json'):
                    response_text = response_text[4:]
            
            validation = json.loads(response_text.strip())
            
            return validation
            
        except Exception as e:
            logger.error(f"Error in validate_prediction_quality: {e}")
            return None
    
    def generate_comprehensive_analysis(self, weather_data: Dict, historical_data: List[Dict]) -> Dict:
        """
        Generate complete multi-factor analysis
        Checks for freeze, hurricane, disease, drought simultaneously
        """
        
        logger.info("Generating comprehensive weather-agriculture analysis...")
        
        analysis = {
            'timestamp': datetime.utcnow().isoformat(),
            'county': weather_data.get('county', 'Unknown'),
            'predictions': [],
            'aggregate_risk': {
                'total_expected_damage_pct': 0,
                'highest_confidence_event': None,
                'timeline': {}
            }
        }
        
        # 1. Check for freeze risk
        freeze_risk = weather_data.get('freeze_risk', {})
        if freeze_risk.get('risk') != 'none':
            logger.info("Freeze risk detected - analyzing...")
            freeze_prediction = self.analyze_freeze_event(weather_data, historical_data)
            if freeze_prediction:
                analysis['predictions'].append(freeze_prediction)
                analysis['aggregate_risk']['total_expected_damage_pct'] += freeze_prediction['expected_crop_damage_pct']
        
        # 2. Check for hurricane threat
        # (Would integrate with hurricane data if available)
        
        # 3. Check for disease pressure
        # (Would check temperature/humidity patterns)
        
        # Find highest confidence prediction
        if analysis['predictions']:
            analysis['aggregate_risk']['highest_confidence_event'] = max(
                analysis['predictions'],
                key=lambda x: x['confidence_score']
            )
        
        logger.info(f"Comprehensive analysis complete: {len(analysis['predictions'])} predictions generated")
        
        return analysis
    
    def explain_prediction_to_user(self, prediction: Dict) -> str:
        """
        Generate human-readable explanation of prediction
        """
        
        prompt = f"""Translate this technical prediction into clear, accessible language.

TECHNICAL PREDICTION:
{json.dumps(prediction, indent=2)}

YOUR TASK:
Explain this prediction in 3-4 paragraphs for a general audience:

Paragraph 1: What is being predicted (event, timing, impact)
Paragraph 2: Why this prediction is being made (key weather factors)
Paragraph 3: Confidence level and what could change
Paragraph 4: What happens next (when we'll know if prediction is correct)

Use simple language. Avoid jargon. Be precise about numbers and timelines.
"""
        
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                temperature=0.2,
                system="You are a science communicator explaining agricultural weather predictions to a general audience.",
                messages=[{"role": "user", "content": prompt}]
            )
            
            return message.content[0].text
            
        except Exception as e:
            logger.error(f"Error generating explanation: {e}")
            return "Error generating explanation"


def main():
    """Test the Claude analysis engine"""
    
    print("="*80)
    print("AgriQuant AI - Claude Sonnet 4 Analysis Engine Test")
    print("="*80)
    
    # Create mock weather data for testing
    mock_forecast = {
        'county': 'Polk',
        'generated_at': datetime.utcnow().isoformat(),
        'freeze_risk': {
            'risk': 'severe_damage',
            'details': {
                'severity': 'severe_damage',
                'start_time': '2026-01-15T06:00:00Z',
                'temperature': 24,
                'duration_hours': 5,
                'expected_damage_pct': 0.15,
                'wind_speed': '5-10 mph'
            },
            'max_expected_damage': 0.15
        },
        'hourly_forecast': [
            {
                'time': '2026-01-15T06:00:00Z',
                'temperature': 24,
                'wind_speed': '5 mph',
                'short_forecast': 'Clear and very cold'
            },
            {
                'time': '2026-01-15T07:00:00Z',
                'temperature': 23,
                'wind_speed': '5 mph',
                'short_forecast': 'Clear and very cold'
            }
        ],
        'discussion': 'Arctic air mass continues to deepen. Surface temps in agricultural regions expected to fall into low-mid 20s for 4-6 hours Wednesday morning.'
    }
    
    mock_historical = [
        {
            'date': '2024-01-16',
            'event_type': 'freeze',
            'min_temp': 26,
            'duration_hours': 5,
            'crop_damage_actual': 0.113,
            'similarity_score': 0.87
        }
    ]
    
    # Initialize engine
    engine = ClaudeAnalysisEngine()
    
    # Test 1: Freeze analysis
    print("\n[TEST 1] Analyzing freeze event with Claude Sonnet 4...")
    prediction = engine.analyze_freeze_event(mock_forecast, mock_historical)
    
    if prediction:
        print(f"✓ Prediction generated successfully")
        print(f"\nPREDICTION SUMMARY:")
        print(f"  Event: {prediction.get('event_type', 'N/A')}")
        print(f"  Probability: {prediction.get('probability', 0)*100:.0f}%")
        print(f"  Expected damage: {prediction.get('expected_crop_damage_pct', 0)*100:.1f}%")
        print(f"  Confidence: {prediction.get('confidence_score', 0)*100:.0f}%")
        print(f"  Tokens used: {prediction.get('tokens_used', 'N/A')}")
        print(f"\nREASONING:")
        print(f"  {prediction.get('reasoning', 'N/A')[:300]}...")
    
    # Test 2: Validate prediction quality
    if prediction:
        print("\n[TEST 2] Validating prediction quality...")
        validation = engine.validate_prediction_quality(prediction)
        
        if validation:
            print(f"✓ Validation complete")
            print(f"  Quality score: {validation.get('quality_score', 0)*100:.0f}%")
            print(f"  Strengths: {validation.get('strengths', [])}")
            print(f"  Weaknesses: {validation.get('weaknesses', [])}")
    
    # Test 3: Generate user-friendly explanation
    if prediction:
        print("\n[TEST 3] Generating user-friendly explanation...")
        explanation = engine.explain_prediction_to_user(prediction)
        print(f"\nEXPLANATION FOR USERS:")
        print(f"{explanation}")
    
    print("\n" + "="*80)
    print("Claude analysis engine test complete!")
    print("="*80)


if __name__ == "__main__":
    main()
