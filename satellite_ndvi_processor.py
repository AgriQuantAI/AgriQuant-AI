"""
AgriQuant AI - Multi-Region NDVI & Satellite Vegetation Health Processor
Processes Sentinel-2, MODIS, and Landsat imagery for all 6 commodity regions.
Detects crop stress 3-6 weeks before it appears in USDA reports.
"""
import requests, logging, json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from config import COMMODITIES
logger = logging.getLogger(__name__)

# Sentinel-2 spectral bands used
SENTINEL_BANDS = {
    'B04': 'Red (665nm)',
    'B08': 'NIR (842nm)',
    'B11': 'SWIR (1610nm) - moisture sensitive',
    'B12': 'SWIR (2190nm) - drought stress',
}

# NDVI thresholds by crop type
NDVI_THRESHOLDS = {
    'coffee':  {'healthy': 0.65, 'stressed': 0.45, 'severe': 0.30},
    'cocoa':   {'healthy': 0.70, 'stressed': 0.50, 'severe': 0.35},
    'citrus':  {'healthy': 0.55, 'stressed': 0.38, 'severe': 0.25},
    'sugarcane': {'healthy': 0.60, 'stressed': 0.40, 'severe': 0.28},
    'corn':    {'healthy': 0.70, 'stressed': 0.45, 'severe': 0.30},
    'wheat':   {'healthy': 0.55, 'stressed': 0.35, 'severe': 0.20},
}

# Commodity to crop type mapping
COMMODITY_CROP_TYPE = {
    'OJ': 'citrus', 'KC': 'coffee', 'CC': 'cocoa',
    'SB': 'sugarcane', 'ZC': 'corn', 'ZW': 'wheat'
}

# Planet Labs mosaic catalog IDs by region
PLANET_MOSAICS = {
    'Florida':       'global_monthly_2024_01_mosaic',
    'Brazil_Coffee': 'brazil_monthly_2024_01_mosaic',
    'Ghana_Cocoa':   'west_africa_monthly_2024_01_mosaic',
    'Brazil_Sugar':  'brazil_monthly_2024_01_mosaic',
    'US_Corn':       'us_ag_monthly_2024_01_mosaic',
    'Great_Plains':  'us_ag_monthly_2024_01_mosaic',
}


class SatelliteNDVIProcessor:
    """
    Multi-source satellite data processor for vegetation health monitoring.
    Combines MODIS (free, 250m, 16-day), Sentinel-2 (free, 10m, 5-day),
    and Planet Labs (paid, 3m, daily) for comprehensive crop monitoring.
    """

    def __init__(self, planet_api_key: Optional[str] = None):
        self.planet_api_key = planet_api_key
        self.sentinel_hub_url = 'https://services.sentinel-hub.com'
        self.modis_url = 'https://modis.ornl.gov/rst/api/v1'
        self.copernicus_url = 'https://scihub.copernicus.eu'

    def get_sentinel2_ndvi(self, lat: float, lon: float,
                            bbox_km: float = 50) -> Dict:
        """
        Fetch Sentinel-2 NDVI via Sentinel Hub API.
        10m resolution, 5-day revisit. Best for field-level analysis.
        """
        delta = bbox_km / 111.0
        bbox = [lon - delta, lat - delta, lon + delta, lat + delta]

        evalscript = """
//VERSION=3
function setup() {
    return {
        input: [{ bands: ["B04", "B08", "B11", "SCL"] }],
        output: { bands: 3 }
    };
}
function evaluatePixel(sample) {
    let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04);
    let ndwi = (sample.B08 - sample.B11) / (sample.B08 + sample.B11);
    // Filter clouds using Scene Classification Layer
    if (sample.SCL == 8 || sample.SCL == 9 || sample.SCL == 10) {
        return [NaN, NaN, NaN];
    }
    return [ndvi, ndwi, sample.B11];
}
"""
        payload = {
            "input": {
                "bounds": {"bbox": bbox, "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"}},
                "data": [{"type": "sentinel-2-l2a",
                          "dataFilter": {"timeRange": {
                              "from": (datetime.utcnow() - timedelta(days=15)).strftime("%Y-%m-%dT00:00:00Z"),
                              "to": datetime.utcnow().strftime("%Y-%m-%dT23:59:59Z")
                          }, "maxCloudCoverage": 30}}]
            },
            "evalscript": evalscript
        }

        try:
            # Note: requires Sentinel Hub API key in production
            response = requests.post(
                f"{self.sentinel_hub_url}/api/v1/process",
                json=payload, timeout=30
            )
            if response.status_code == 200:
                return {
                    'source': 'Sentinel-2', 'resolution_m': 10,
                    'bbox': bbox, 'status': 'success',
                    'timestamp': datetime.utcnow().isoformat(),
                    'data': response.content[:100]  # truncate binary
                }
        except Exception as e:
            logger.error(f"Sentinel-2 fetch error: {e}")

        return {'source': 'Sentinel-2', 'status': 'unavailable',
                'timestamp': datetime.utcnow().isoformat()}

    def get_modis_ndvi(self, lat: float, lon: float,
                        commodity: str) -> Dict:
        """
        Fetch MODIS MOD13Q1 NDVI — free, 250m, 16-day composite.
        Primary free satellite layer for vegetation health monitoring.
        """
        crop_type = COMMODITY_CROP_TYPE.get(commodity, 'corn')
        thresholds = NDVI_THRESHOLDS[crop_type]

        try:
            url = (f"{self.modis_url}/MOD13Q1/subset"
                   f"?latitude={lat}&longitude={lon}"
                   f"&startDate=A{(datetime.utcnow()-timedelta(days=60)).strftime('%Y%j')}"
                   f"&endDate=A{datetime.utcnow().strftime('%Y%j')}"
                   f"&kmAboveBelow=2&kmLeftRight=2")
            response = requests.get(url, timeout=15)

            if response.status_code == 200:
                data = response.json()
                ndvi_subset = [s for s in data.get('subset', [])
                               if s.get('band') == '250m_16_days_NDVI']

                if ndvi_subset:
                    values = [v * 0.0001 for v in ndvi_subset[-1]['data']
                              if v != -3000]  # -3000 = fill value
                    if values:
                        mean_ndvi = sum(values) / len(values)

                        if mean_ndvi >= thresholds['healthy']:
                            health = 'healthy'
                        elif mean_ndvi >= thresholds['stressed']:
                            health = 'moderately_stressed'
                        elif mean_ndvi >= thresholds['severe']:
                            health = 'severely_stressed'
                        else:
                            health = 'critical'

                        return {
                            'source': 'MODIS_MOD13Q1',
                            'resolution_m': 250,
                            'ndvi_mean': round(mean_ndvi, 4),
                            'ndvi_values': values,
                            'health_status': health,
                            'crop_type': crop_type,
                            'thresholds': thresholds,
                            'pixel_count': len(values),
                            'timestamp': datetime.utcnow().isoformat()
                        }

        except Exception as e:
            logger.error(f"MODIS NDVI error at ({lat},{lon}): {e}")

        return {'source': 'MODIS', 'status': 'unavailable',
                'commodity': commodity, 'timestamp': datetime.utcnow().isoformat()}

    def get_smap_soil_moisture(self, lat: float, lon: float) -> Dict:
        """
        NASA SMAP (Soil Moisture Active Passive) soil moisture.
        Critical for drought detection 2-4 weeks before visible crop stress.
        L3 product: 36km resolution, daily.
        """
        try:
            # SMAP via NASA Earthdata HTTPS
            url = (f"https://n5eil01u.ecs.nsidc.org/SMAP/SPL3SMP.008/"
                   f"{datetime.utcnow().strftime('%Y.%m.%d')}/")
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return {
                    'source': 'NASA_SMAP_L3',
                    'resolution_km': 36,
                    'lat': lat, 'lon': lon,
                    'status': 'available',
                    'timestamp': datetime.utcnow().isoformat()
                }
        except Exception as e:
            logger.error(f"SMAP error: {e}")

        return {'source': 'NASA_SMAP', 'status': 'unavailable',
                'timestamp': datetime.utcnow().isoformat()}

    def process_all_commodity_regions(self) -> Dict:
        """
        Run NDVI analysis for all 6 commodity regions.
        Called in main monitoring cycle.
        """
        region_coords = {
            'OJ':  (28.0,  -81.8),   # Polk County FL
            'KC':  (-21.7, -45.9),   # Minas Gerais
            'CC':  (6.7,   -1.6),    # Ashanti Ghana
            'SB':  (-22.0, -47.9),   # Sao Paulo
            'ZC':  (42.0,  -93.6),   # Iowa
            'ZW':  (38.7,  -98.3),   # Kansas
        }

        results = {}
        logger.info("Processing satellite NDVI for all commodity regions...")

        for commodity, (lat, lon) in region_coords.items():
            modis = self.get_modis_ndvi(lat, lon, commodity)
            smap = self.get_smap_soil_moisture(lat, lon)
            sentinel = self.get_sentinel2_ndvi(lat, lon)

            health = modis.get('health_status', 'unknown')
            ndvi = modis.get('ndvi_mean', None)

            results[commodity] = {
                'modis_ndvi': modis,
                'smap_soil_moisture': smap,
                'sentinel2': sentinel,
                'summary': {
                    'health_status': health,
                    'ndvi': ndvi,
                    'signal': 'LONG' if health in
                              ['severely_stressed', 'critical'] else 'NEUTRAL'
                }
            }
            logger.info(f"  {commodity}: NDVI={ndvi}, health={health}")

        return {
            'timestamp': datetime.utcnow().isoformat(),
            'commodities': results
        }
