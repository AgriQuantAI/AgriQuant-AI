"""
AgriQuant AI - El Nino / La Nina Monitor
ENSO (El Nino Southern Oscillation) is the single biggest driver of
correlated weather events across ALL 6 commodity regions simultaneously.
El Nino: dry in tropics (KC, CC, SB), wet in Brazil Center-South (mixed SB),
         drought in India (SB), wet in US South (mixed ZW)
La Nina: opposite effects
"""
import requests, logging
from datetime import datetime, timedelta
from typing import Dict, List
logger = logging.getLogger(__name__)

# ENSO phase commodity impact table (directional guidance)
ENSO_COMMODITY_IMPACTS = {
    'el_nino': {
        'OJ':  {'direction': 'LONG',    'magnitude': 'moderate', 'lag_months': 3,
                'reason': 'Florida drought risk, reduced irrigation'},
        'KC':  {'direction': 'LONG',    'magnitude': 'high',     'lag_months': 4,
                'reason': 'Brazil frost risk elevated, dry season extends'},
        'CC':  {'direction': 'LONG',    'magnitude': 'high',     'lag_months': 3,
                'reason': 'West Africa Harmattan intensifies, Ghana/IC drought'},
        'SB':  {'direction': 'LONG',    'magnitude': 'moderate', 'lag_months': 4,
                'reason': 'India monsoon deficient, Thailand drought'},
        'ZC':  {'direction': 'NEUTRAL', 'magnitude': 'low',      'lag_months': 2,
                'reason': 'Mixed US Midwest impact'},
        'ZW':  {'direction': 'SHORT',   'magnitude': 'low',      'lag_months': 2,
                'reason': 'Wetter conditions favorable for HRW winter wheat'},
    },
    'la_nina': {
        'OJ':  {'direction': 'NEUTRAL', 'magnitude': 'low',      'lag_months': 3,
                'reason': 'Wetter Florida, reduced freeze risk'},
        'KC':  {'direction': 'SHORT',   'magnitude': 'moderate', 'lag_months': 4,
                'reason': 'Cooler Brazil, good moisture for Arabica'},
        'CC':  {'direction': 'SHORT',   'magnitude': 'moderate', 'lag_months': 3,
                'reason': 'Better West Africa rains, reduced drought'},
        'SB':  {'direction': 'SHORT',   'magnitude': 'moderate', 'lag_months': 4,
                'reason': 'India excess monsoon, Thailand flooding risk'},
        'ZC':  {'direction': 'LONG',    'magnitude': 'moderate', 'lag_months': 2,
                'reason': 'US Plains drought, Midwest dry conditions'},
        'ZW':  {'direction': 'LONG',    'magnitude': 'moderate', 'lag_months': 2,
                'reason': 'Great Plains drought, HRW production risk'},
    },
    'neutral': {c: {'direction': 'NEUTRAL', 'magnitude': 'none', 'lag_months': 0,
                    'reason': 'No ENSO signal'} for c in ['OJ','KC','CC','SB','ZC','ZW']}
}


class ElNinoMonitor:
    """
    Monitors ENSO phase using NOAA Climate Prediction Center (CPC) data.
    Oni Index (Oceanic Nino Index): 3-month running mean of SST anomalies
    in Nino 3.4 region (5N-5S, 120-170W).
    El Nino: ONI >= +0.5C for 5+ consecutive seasons
    La Nina: ONI <= -0.5C for 5+ consecutive seasons
    """

    def __init__(self):
        self.cpc_base = 'https://www.cpc.ncep.noaa.gov'
        self.noaa_enso = 'https://origin.cpc.ncep.noaa.gov/products/analysis_monitoring/ensostuff'

    def get_oni_index(self) -> Dict:
        """
        Fetch current ONI (Oceanic Nino Index) from NOAA CPC.
        This is the definitive ENSO indicator.
        """
        try:
            url = f"{self.noaa_enso}/ONI_v5.php"
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                return {
                    'source': 'NOAA_CPC_ONI',
                    'url': url,
                    'status': 'fetched',
                    'timestamp': datetime.utcnow().isoformat(),
                    'note': 'Parse HTML table for ONI values in production'
                }
        except Exception as e:
            logger.error(f"ONI fetch error: {e}")

        return {'source': 'NOAA_CPC_ONI', 'status': 'unavailable',
                'timestamp': datetime.utcnow().isoformat()}

    def get_enso_forecast(self) -> Dict:
        """
        Fetch ENSO probability forecast from IRI (International Research
        Institute for Climate and Society). 9-month ahead probabilities.
        """
        try:
            iri_url = 'https://iri.columbia.edu/our-expertise/climate/forecasts/enso/current'
            resp = requests.get(iri_url, timeout=10)
            return {
                'source': 'IRI_Columbia',
                'status': 'fetched' if resp.status_code == 200 else 'unavailable',
                'timestamp': datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {'source': 'IRI_Columbia', 'status': 'unavailable',
                    'error': str(e), 'timestamp': datetime.utcnow().isoformat()}

    def classify_enso_phase(self, oni_value: float) -> str:
        """Classify current ENSO phase from ONI value"""
        if oni_value >= 1.5:
            return 'strong_el_nino'
        elif oni_value >= 0.5:
            return 'el_nino'
        elif oni_value <= -1.5:
            return 'strong_la_nina'
        elif oni_value <= -0.5:
            return 'la_nina'
        else:
            return 'neutral'

    def get_commodity_signals(self, oni_value: float) -> Dict:
        """
        Generate commodity trading signals based on ENSO phase.
        These are medium-term (3-6 month) directional biases.
        """
        phase = self.classify_enso_phase(oni_value)
        base_phase = 'el_nino' if 'el_nino' in phase else \
                     ('la_nina' if 'la_nina' in phase else 'neutral')
        impacts = ENSO_COMMODITY_IMPACTS[base_phase]

        strength_multiplier = min(2.0, abs(oni_value) / 0.5)

        signals = {}
        for commodity, impact in impacts.items():
            signals[commodity] = {
                **impact,
                'enso_phase': phase,
                'oni_value': oni_value,
                'strength_multiplier': round(strength_multiplier, 2),
                'time_horizon': 'medium_term_3_6_months',
            }

        return {
            'enso_phase': phase,
            'oni_value': oni_value,
            'commodity_signals': signals,
            'highest_impact': sorted(
                [(c, i['magnitude']) for c, i in impacts.items()],
                key=lambda x: ['none','low','moderate','high'].index(x[1]),
                reverse=True
            )[:3],
            'timestamp': datetime.utcnow().isoformat()
        }

    def run(self) -> Dict:
        """Full ENSO monitoring cycle"""
        logger.info("Running ENSO monitor...")
        oni_data = self.get_oni_index()
        forecast = self.get_enso_forecast()

        # In production: parse oni_value from CPC data
        # Using example moderate El Nino for demonstration
        oni_value = 0.8
        signals = self.get_commodity_signals(oni_value)

        return {
            'timestamp': datetime.utcnow().isoformat(),
            'oni_data': oni_data,
            'enso_forecast': forecast,
            'current_signals': signals,
        }
