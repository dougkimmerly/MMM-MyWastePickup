#!/usr/bin/env python3
"""
Toronto Garbage Collection Schedule Checker

For: 55 Tenth Street, South Etobicoke (District 1)

Usage:
    python toronto_garbage.py              # Show upcoming collections
    python toronto_garbage.py --next       # Show just the next collection
    python toronto_garbage.py --weeks 8    # Show next 8 weeks
    
Data source: Toronto Open Data Portal
https://open.toronto.ca/dataset/solid-waste-pickup-schedule/
"""

import json
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from typing import Optional
import argparse

# ============================================================
# CONFIGURATION - Update this to match your schedule!
# ============================================================
# After checking toronto.ca or the TOwaste app with your address,
# set this to either "Wednesday 1" or "Wednesday 2"
CALENDAR = "Wednesday 1"  # 55 Tenth Street, South Etobicoke
# ============================================================

# Toronto Open Data API
API_BASE = "https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/datastore_search"

# Resource IDs for each year's schedule data
RESOURCES = {
    2025: "c801b084-b3c4-43a8-ba25-b94531e75863",
    2026: "47416395-fb31-4252-9737-2367f5a56953",
}


def fetch_schedule(calendar: str, start_date: datetime, weeks: int = 4) -> list[dict]:
    """Fetch garbage schedule from Toronto Open Data API."""
    
    results = []
    end_date = start_date + timedelta(weeks=weeks)
    
    # Determine which year(s) we need data for
    years_needed = set()
    current = start_date
    while current <= end_date:
        years_needed.add(current.year)
        current += timedelta(days=7)
    
    for year in sorted(years_needed):
        resource_id = RESOURCES.get(year)
        if not resource_id:
            print(f"⚠️  No schedule data available for {year}")
            continue
        
        # Build API query
        filters = json.dumps({"Calendar": calendar})
        url = (
            f"{API_BASE}?"
            f"resource_id={resource_id}&"
            f"filters={urllib.parse.quote(filters)}&"
            f"limit=100"
        )
        
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Toronto-Garbage-Checker/1.0'})
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.loads(response.read().decode('utf-8'))
                
            if data.get('success'):
                records = data['result']['records']
                
                for record in records:
                    week_start = datetime.strptime(record['WeekStarting'], '%Y-%m-%d')
                    if start_date <= week_start <= end_date:
                        results.append({
                            'date': week_start,
                            'green_bin': record.get('GreenBin', '0'),
                            'garbage': record.get('Garbage', '0'),
                            'recycling': record.get('Recycling', '0'),
                            'yard_waste': record.get('YardWaste', '0'),
                            'christmas_tree': record.get('ChristmasTree', '0'),
                        })
                        
        except urllib.error.URLError as e:
            print(f"⚠️  Network error: {e}")
        except json.JSONDecodeError as e:
            print(f"⚠️  Error parsing response: {e}")
        except Exception as e:
            print(f"⚠️  Error fetching schedule: {e}")
    
    results.sort(key=lambda x: x['date'])
    return results


def format_collection(record: dict) -> tuple[str, list[str]]:
    """Format a single collection day. Returns (date_str, list of items)."""
    
    date_str = record['date'].strftime('%A, %B %d, %Y')
    items = []
    
    # Green bin collected every week (check for day letter like 'W' for Wednesday)
    if record['green_bin'] and record['green_bin'] not in ['0', '']:
        items.append("🟢 Green Bin (Organics)")
    
    # Garbage alternates with recycling
    if record['garbage'] and record['garbage'] not in ['0', '']:
        items.append("⬛ Garbage")
    
    if record['recycling'] and record['recycling'] not in ['0', '']:
        items.append("🔵 Blue Bin (Recycling)")
    
    # Yard waste (seasonal - roughly mid-March to mid-December)
    if record['yard_waste'] and record['yard_waste'] not in ['0', '']:
        items.append("🟤 Yard Waste")
    
    # Christmas trees (January only)
    if record['christmas_tree'] and record['christmas_tree'] not in ['0', '']:
        items.append("🎄 Christmas Tree")
    
    return date_str, items


def print_schedule(records: list[dict], show_all: bool = True):
    """Print the collection schedule."""
    
    if not records:
        print("No schedule data found for the specified period.")
        return
    
    print(f"\n📅 Garbage Collection Schedule for {CALENDAR}")
    print(f"   55 Tenth Street, South Etobicoke")
    print("=" * 50)
    
    for record in records:
        date_str, items = format_collection(record)
        
        if items:
            print(f"\n{date_str}")
            for item in items:
                print(f"  {item}")
        elif show_all:
            print(f"\n{date_str}")
            print("  (No collection scheduled)")


def get_next_collection(records: list[dict]) -> Optional[dict]:
    """Get the next collection with items."""
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    for record in records:
        if record['date'] >= today:
            _, items = format_collection(record)
            if items:
                return record
    return None


def main():
    parser = argparse.ArgumentParser(description='Check Toronto garbage collection schedule')
    parser.add_argument('--weeks', type=int, default=4, help='Number of weeks to show (default: 4)')
    parser.add_argument('--next', action='store_true', help='Show only the next collection')
    parser.add_argument('--calendar', type=str, help='Override calendar (e.g., "Wednesday 1")')
    args = parser.parse_args()
    
    calendar = args.calendar or CALENDAR
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    print(f"🔄 Fetching schedule from Toronto Open Data...")
    records = fetch_schedule(calendar, today, args.weeks)
    
    if args.next:
        next_collection = get_next_collection(records)
        if next_collection:
            date_str, items = format_collection(next_collection)
            print(f"\n📅 Next Collection: {date_str}")
            for item in items:
                print(f"  {item}")
        else:
            print("No upcoming collections found.")
    else:
        print_schedule(records)
    
    print("\n" + "=" * 50)
    print("ℹ️  Data from: Toronto Open Data Portal")
    print("🔗 https://open.toronto.ca/dataset/solid-waste-pickup-schedule/")


if __name__ == "__main__":
    main()
