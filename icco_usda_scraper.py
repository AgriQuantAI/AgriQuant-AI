"""
AgriQuant AI - Supply Report Monitor
Monitors USDA WASDE, USDA Crop Progress, ICCO supply/demand,
ICO coffee reports, and CONAB Brazil estimates for all 6 commodities.
Detects supply revisions before they hit futures markets.
"""
import requests, logging
from datetime import datetime
from typing import Dict, List
logger = logging.getLogger(__name__)

# USDA WASDE release calendar (monthly, typically 2nd Tuesday)
WASDE_URL = 'https://apps.fas.usda.gov/psdonline/app/index.html#/app/downloads'
USDA_NASS_API = 'https://quickstats.nass.usda.gov/api'
USDA_CROP_PROGRESS = 'https://release.nass.usda.gov/reports/prog'

# ICO (International Coffee Organization) data
ICO_BASE = 'https://icocoffee.org/resources/trade-statistics'

# ICCO (International Cocoa Organization) data
ICCO_BASE = 'https://www.icco.org/statistics'

# CONAB (Brazil national supply agency)
CONAB_BASE = 'https://www.conab.gov.br'

REPORT_SCHEDULE = {
    'WASDE':         {'frequency': 'monthly', 'day': '2nd Tuesday',
                      'commodities': ['OJ','KC','CC','SB','ZC','ZW']},
    'Crop_Progress': {'frequency': 'weekly',  'day': 'Monday',
                      'commodities': ['ZC','ZW']},
    'CONAB_Coffee':  {'frequency': 'monthly', 'day': 'varies',
                      'commodities': ['KC']},
    'ICCO_Quarterly':{'frequency': 'quarterly','day': 'varies',
                      'commodities': ['CC']},
    'ICO_Monthly':   {'frequency': 'monthly', 'day': 'varies',
                      'commodities': ['KC']},
    'USDA_Citrus':   {'frequency': 'monthly', 'day': '1st Friday',
                      'commodities': ['OJ']},
}


class SupplyReportMonitor:
    """
    Monitors and ingests supply/demand reports from all relevant agencies.
    Detects revision magnitude to assess price impact before market open.
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'AgriQuant-AI/1.0'})

    def fetch_usda_wasde(self) -> Dict:
        """
        Fetch latest USDA WASDE (World Agricultural Supply and Demand Estimates).
        Published monthly. Contains S&D estimates for all grain and oilseed markets.
        Critical for ZC, ZW, SB signals.
        """
        try:
            resp = self.session.get(WASDE_URL, timeout=15)
            return {
                'report': 'USDA_WASDE',
                'status': 'fetched' if resp.status_code == 200 else 'failed',
                'commodities_covered': ['ZC', 'ZW', 'SB', 'KC', 'CC'],
                'timestamp': datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"WASDE fetch error: {e}")
            return {'report': 'USDA_WASDE', 'status': 'error', 'error': str(e)}

    def fetch_usda_crop_progress(self, commodity: str,
                                  state: str = None) -> Dict:
        """
        Weekly USDA Crop Progress report.
        Released every Monday during growing season.
        Good/Excellent % is the single most market-moving weekly ag data point.
        A 5+ point drop week-over-week = significant futures move.
        """
        try:
            params = {
                'key': 'DEMO_KEY',
                'commodity_desc': 'CORN' if commodity == 'ZC' else 'WHEAT',
                'statisticcat_desc': 'CONDITION',
                'unit_desc': 'PCT EXCELLENT',
                'year__GE': str(datetime.utcnow().year),
                'format': 'JSON'
            }
            if state:
                params['state_name'] = state.upper()

            resp = requests.get(f"{USDA_NASS_API}/api_GET/",
                                params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json().get('data', [])
                if len(data) >= 2:
                    latest = float(data[-1].get('Value', 0))
                    prior = float(data[-2].get('Value', 0))
                    delta = latest - prior
                    signal = ('LONG' if delta < -5 else
                              'SHORT' if delta > 5 else 'NEUTRAL')
                    return {
                        'commodity': commodity, 'latest_pct_excellent': latest,
                        'prior_pct_excellent': prior, 'week_over_week_delta': delta,
                        'signal': signal,
                        'note': 'Delta < -5 = bullish (crop deteriorating)',
                        'source': 'USDA_NASS', 'timestamp': datetime.utcnow().isoformat()
                    }
        except Exception as e:
            logger.error(f"Crop progress error: {e}")

        return {'commodity': commodity, 'source': 'USDA_NASS', 'status': 'unavailable'}

    def fetch_conab_coffee_estimate(self) -> Dict:
        """
        CONAB (Brazil's national supply agency) monthly coffee crop estimates.
        CONAB revisions often move KC 2-5% on release day.
        """
        try:
            resp = self.session.get(
                f"{CONAB_BASE}/safras/safra-cafe", timeout=10
            )
            return {
                'source': 'CONAB_Brazil', 'commodity': 'KC',
                'status': 'fetched' if resp.status_code == 200 else 'unavailable',
                'note': 'Parse million 60kg bags estimate in production',
                'timestamp': datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {'source': 'CONAB_Brazil', 'status': 'error',
                    'error': str(e), 'timestamp': datetime.utcnow().isoformat()}

    def fetch_icco_supply_data(self) -> Dict:
        """
        ICCO quarterly supply/demand data for cocoa.
        Deficit/surplus estimate is the primary CC price driver.
        2023-24 saw record deficit — what ICCO flagged moved CC +115%.
        """
        try:
            resp = self.session.get(ICCO_BASE, timeout=10)
            return {
                'source': 'ICCO', 'commodity': 'CC',
                'status': 'fetched' if resp.status_code == 200 else 'unavailable',
                'note': 'Parse global grindings and production deficit in production',
                'timestamp': datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {'source': 'ICCO', 'status': 'error', 'error': str(e)}

    def assess_revision_impact(self, commodity: str,
                                prior_estimate: float,
                                new_estimate: float,
                                unit: str = 'million_tons') -> Dict:
        """
        Assess price impact of a supply revision.
        Larger revisions in tighter markets = larger price moves.
        """
        revision_pct = ((new_estimate - prior_estimate) / prior_estimate) * 100

        # Supply cut = bullish; supply increase = bearish
        if revision_pct < -5:
            direction, impact = 'LONG',  abs(revision_pct) * 0.8
        elif revision_pct < -2:
            direction, impact = 'LONG',  abs(revision_pct) * 0.5
        elif revision_pct > 5:
            direction, impact = 'SHORT', abs(revision_pct) * 0.6
        elif revision_pct > 2:
            direction, impact = 'SHORT', abs(revision_pct) * 0.3
        else:
            direction, impact = 'NEUTRAL', 0.0

        return {
            'commodity': commodity,
            'prior_estimate': prior_estimate,
            'new_estimate': new_estimate,
            'unit': unit,
            'revision_pct': round(revision_pct, 2),
            'signal_direction': direction,
            'estimated_price_impact_pct': round(impact, 1),
            'timestamp': datetime.utcnow().isoformat()
        }

    def run_all_reports(self) -> Dict:
        """Fetch all available supply reports"""
        logger.info("Fetching supply reports from all agencies...")
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'wasde': self.fetch_usda_wasde(),
            'crop_progress_corn': self.fetch_usda_crop_progress('ZC'),
            'crop_progress_wheat': self.fetch_usda_crop_progress('ZW'),
            'conab_coffee': self.fetch_conab_coffee_estimate(),
            'icco_cocoa': self.fetch_icco_supply_data(),
        }
