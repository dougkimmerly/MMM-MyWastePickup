#!/usr/bin/env python3
"""
Toronto Garbage Collection Schedule Checker (CSV Version)

For: 55 Tenth Street, South Etobicoke (District 1)

This version downloads the CSV file directly which tends to be more reliable.

Usage:
    python toronto_garbage_csv.py              # Show upcoming collections  
    python toronto_garbage_csv.py --refresh    # Force re-download of schedule data
    python toronto_garbage_csv.py --next       # Show just the next collection

Data source: Toronto Open Data Portal
https://open.toronto.ca/dataset/solid-waste-pickup-schedule/
"""

import csv
import os
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
import argparse

# ============================================================
# CONFIGURATION - Update this to match your schedule!
# ============================================================
# After checking toronto.ca or the TOwaste app with your address,
# set this to either "Wednesday 1" or "Wednesday 2"
CALENDAR = "Wednesday2"  # 55 Tenth Street, South Etobicoke
# ============================================================

# CSV download URLs from Toronto Open Data
CSV_URLS = {
    2025: "https://ckan0.cf.opendata.inter.prod-toronto.ca/dataset/7b70189a-aede-42f1-b092-8708fa4f5fc3/resource/d78c77fe-6055-44d1-836b-e2d36722b3ce/download/pickup-schedule-2025.csv",
    2026: "https://ckan0.cf.opendata.inter.prod-toronto.ca/dataset/7b70189a-aede-42f1-b092-8708fa4f5fc3/resource/fe6f168c-4d5e-4b62-856b-3306a0fe56dd/download/pickup-schedule-2026.csv",
}

# Cache directory
CACHE_DIR = Path.home() / ".toronto_garbage_cache"


def ensure_cache_dir():
    """Create cache directory if it doesn't exist."""
    CACHE_DIR.mkdir(exist_ok=True)


def get_cache_path(year: int) -> Path:
    """Get the cache file path for a year."""
    return CACHE_DIR / f"pickup-schedule-{year}.csv"


def is_cache_fresh(year: int, max_age_days: int = 7) -> bool:
    """Check if cached file is fresh enough."""
    cache_path = get_cache_path(year)
    if not cache_path.exists():
        return False
    
    mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
    age = datetime.now() - mtime
    return age.days < max_age_days


def download_schedule(year: int, force: bool = False) -> Path:
    """Download schedule CSV for a year, using cache if available."""
    ensure_cache_dir()
    cache_path = get_cache_path(year)
    
    if not force and is_cache_fresh(year):
        print(f"📁 Using cached {year} schedule")
        return cache_path
    
    url = CSV_URLS.get(year)
    if not url:
        raise ValueError(f"No schedule URL available for {year}")
    
    print(f"⬇️  Downloading {year} schedule...")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Toronto-Garbage-Checker/1.0'})
        with urllib.request.urlopen(req, timeout=30) as response:
            data = response.read()
        
        with open(cache_path, 'wb') as f:
            f.write(data)
        
        print(f"✅ Downloaded and cached {year} schedule")
        return cache_path
        
    except Exception as e:
        if cache_path.exists():
            print(f"⚠️  Download failed, using older cached version: {e}")
            return cache_path
        raise


def load_schedule(year: int, calendar: str, force_refresh: bool = False) -> list[dict]:
    """Load schedule from CSV for a specific calendar."""
    
    try:
        csv_path = download_schedule(year, force=force_refresh)
    except Exception as e:
        print(f"⚠️  Could not get {year} schedule: {e}")
        return []
    
    records = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('Calendar') == calendar:
                try:
                    week_start = datetime.strptime(row['WeekStarting'], '%Y-%m-%d')
                    records.append({
                        'date': week_start,
                        'green_bin': row.get('GreenBin', '0'),
                        'garbage': row.get('Garbage', '0'),
                        'recycling': row.get('Recycling', '0'),
                        'yard_waste': row.get('YardWaste', '0'),
                        'christmas_tree': row.get('ChristmasTree', '0'),
                    })
                except ValueError:
                    continue
    
    return records


def format_collection(record: dict) -> tuple[str, list[str]]:
    """Format a single collection day. Returns (date_str, list of items)."""
    
    date_str = record['date'].strftime('%A, %B %d, %Y')
    items = []
    
    # Green bin collected every week
    if record['green_bin'] and record['green_bin'] not in ['0', '']:
        items.append("🟢 Green Bin (Organics)")
    
    # Garbage alternates with recycling
    if record['garbage'] and record['garbage'] not in ['0', '']:
        items.append("⬛ Garbage")
    
    if record['recycling'] and record['recycling'] not in ['0', '']:
        items.append("🔵 Blue Bin (Recycling)")
    
    # Yard waste (seasonal)
    if record['yard_waste'] and record['yard_waste'] not in ['0', '']:
        items.append("🟤 Yard Waste")
    
    # Christmas trees (January only)
    if record['christmas_tree'] and record['christmas_tree'] not in ['0', '']:
        items.append("🎄 Christmas Tree")
    
    return date_str, items


def get_upcoming_collections(calendar: str, weeks: int = 4, force_refresh: bool = False) -> list[dict]:
    """Get upcoming collections for the specified period."""
    
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = today + timedelta(weeks=weeks)
    
    # Determine which year(s) we need
    years_needed = set()
    current = today
    while current <= end_date:
        years_needed.add(current.year)
        current += timedelta(days=7)
    
    all_records = []
    for year in sorted(years_needed):
        records = load_schedule(year, calendar, force_refresh)
        all_records.extend(records)
    
    # Filter to upcoming dates
    upcoming = [r for r in all_records if today <= r['date'] <= end_date]
    upcoming.sort(key=lambda x: x['date'])
    
    return upcoming


def print_schedule(records: list[dict]):
    """Print the collection schedule."""
    
    if not records:
        print("\n⚠️  No upcoming collections found.")
        return
    
    print(f"\n📅 Garbage Collection Schedule: {CALENDAR}")
    print(f"   55 Tenth Street, South Etobicoke")
    print("=" * 50)
    
    for record in records:
        date_str, items = format_collection(record)
        
        if items:
            # Check if this is the next upcoming collection
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            days_until = (record['date'] - today).days
            
            if days_until == 0:
                marker = " ⭐ TODAY!"
            elif days_until == 1:
                marker = " 📌 Tomorrow"
            elif days_until <= 7:
                marker = f" ({days_until} days)"
            else:
                marker = ""
            
            print(f"\n{date_str}{marker}")
            for item in items:
                print(f"  {item}")


def main():
    parser = argparse.ArgumentParser(description='Check Toronto garbage collection schedule')
    parser.add_argument('--weeks', type=int, default=4, help='Number of weeks to show (default: 4)')
    parser.add_argument('--next', action='store_true', help='Show only the next collection')
    parser.add_argument('--refresh', action='store_true', help='Force re-download of schedule data')
    parser.add_argument('--calendar', type=str, help='Override calendar (e.g., "Wednesday 1")')
    args = parser.parse_args()
    
    calendar = args.calendar or CALENDAR
    
    records = get_upcoming_collections(calendar, args.weeks, args.refresh)
    
    if args.next:
        # Find next collection with items
        for record in records:
            _, items = format_collection(record)
            if items:
                date_str, items = format_collection(record)
                today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                days_until = (record['date'] - today).days
                
                print(f"\n📅 Next Collection: {date_str}")
                if days_until == 0:
                    print("   ⭐ That's TODAY!")
                elif days_until == 1:
                    print("   📌 That's TOMORROW!")
                    
                print("\n   Put out:")
                for item in items:
                    print(f"   {item}")
                break
        else:
            print("\n⚠️  No upcoming collections found.")
    else:
        print_schedule(records)
    
    print("\n" + "=" * 50)
    print(f"📁 Cache location: {CACHE_DIR}")
    print("🔗 Data: Toronto Open Data Portal")


if __name__ == "__main__":
    main()
