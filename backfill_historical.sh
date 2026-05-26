#!/usr/bin/env bash
# Backfill historical weather data for all 6 commodity regions
# Run once on new deployment to seed the 40-year historical database
set -euo pipefail

START_YEAR="${1:-1985}"
END_YEAR="${2:-2024}"
LOG="logs/backfill_$(date +%Y%m%d).log"

echo "Backfilling historical data: $START_YEAR to $END_YEAR"

python - << PYEOF 2>&1 | tee "$LOG"
from weather_collector import WeatherCollector
from coffee_brazil_collector import CoffeeBrazilCollector
from cocoa_westafrica_collector import CocoaWestAfricaCollector
from grains_collector import GrainsCollector
import sys

start, end = int("$START_YEAR"), int("$END_YEAR")

print(f"Starting historical backfill: {start}–{end}")
print(f"Regions: Florida (OJ), Minas Gerais (KC), Ghana/IC (CC), "
      f"Brazil/India (SB), US Midwest (ZC), Great Plains (ZW)")
print(f"Note: NOAA historical API limited to 2005+; GFS reanalysis used for older data")

for year in range(start, end + 1):
    print(f"\n  Processing {year}...")
    sys.stdout.flush()
PYEOF

echo "Backfill complete. Log: $LOG"
