#!/usr/bin/env python3
"""
Generate MMM-MyWastePickup schedule_custom.csv from Toronto Open Data

This script:
1. Downloads the official Toronto waste pickup schedule
2. Converts it to the format expected by MMM-MyWastePickup
3. Handles Toronto's format changes (e.g., missing Recycling column)
4. Can extrapolate/interpolate into future years if Toronto stops publishing

Usage:
    python generate_schedule.py                    # Generate schedule and show preview
    python generate_schedule.py --write            # Write to schedule_custom.csv
    python generate_schedule.py --years 2025 2026  # Specific years
    python generate_schedule.py --extend 2030     # Extend schedule through 2030
    python generate_schedule.py --calendar "Wednesday2"  # Override calendar

For: 55 Tenth Street, South Etobicoke
Calendar: Wednesday2
"""

import csv
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
import argparse

# Configuration
DEFAULT_CALENDAR = "Wednesday2"  # No space in Toronto's format
OUTPUT_FILE = Path(__file__).parent.parent / "schedule_custom.csv"

# Toronto Open Data CSV URLs - update these when Toronto changes them
CSV_URLS = {
    2025: "https://ckan0.cf.opendata.inter.prod-toronto.ca/dataset/7b70189a-aede-42f1-b092-8708fa4f5fc3/resource/d78c77fe-6055-44d1-836b-e2d36722b3ce/download/pickup-schedule-2025.csv",
    2026: "https://ckan0.cf.opendata.inter.prod-toronto.ca/dataset/7b70189a-aede-42f1-b092-8708fa4f5fc3/resource/fe6f168c-4d5e-4b62-856b-3306a0fe56dd/download/pickup-schedule-2026.csv",
}


def download_csv(url: str) -> str:
    """Download CSV using curl (handles SSL better than Python's urllib)."""
    result = subprocess.run(
        ["curl", "-s", url],
        capture_output=True,
        text=True,
        timeout=60
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to download: {result.stderr}")
    return result.stdout


def parse_toronto_csv(csv_data: str, calendar: str) -> list[dict]:
    """
    Parse Toronto's CSV format and convert to MMM-MyWastePickup format.

    Toronto's format (2026):
        _id,Calendar,WeekStarting,GreenBin,Garbage,YardWaste,ChristmasTree

    MMM-MyWastePickup expects:
        Calendar,WeekStarting,GreenBin,Garbage,Recycling,YardWaste,ChristmasTree

    Key insight: Toronto removed "Recycling" column. Recycling is collected
    on weeks when Garbage is NOT collected (alternating bi-weekly).
    """
    records = []
    lines = csv_data.strip().split('\n')

    if not lines:
        return records

    # Parse header to understand column positions
    reader = csv.DictReader(lines)

    for row in reader:
        # Match calendar (Toronto uses "Wednesday1", we might search for "Wednesday 1")
        row_calendar = row.get('Calendar', '')
        if calendar.replace(' ', '') != row_calendar.replace(' ', ''):
            continue

        # Parse date - Toronto uses MM/DD/YY format
        date_str = row.get('WeekStarting', '')

        # Get collection flags
        green_bin = row.get('GreenBin', '0')
        garbage = row.get('Garbage', '0')
        yard_waste = row.get('YardWaste', '0')
        christmas_tree = row.get('ChristmasTree', '0')

        # Toronto 2026 doesn't have Recycling column
        # Recycling is collected on weeks when Garbage is NOT collected
        recycling = row.get('Recycling', '')
        if not recycling:
            # Infer recycling: if no garbage, then recycling
            if garbage in ['0', '', None]:
                recycling = 'W'
            else:
                recycling = '0'

        # Normalize flags to W or 0
        def normalize(val):
            if val and val not in ['0', '']:
                return 'W'
            return '0'

        records.append({
            'Calendar': 'Custom',
            'WeekStarting': date_str,
            'GreenBin': normalize(green_bin),
            'Garbage': normalize(garbage),
            'Recycling': normalize(recycling),
            'YardWaste': normalize(yard_waste),
            'ChristmasTree': normalize(christmas_tree),
        })

    return records


def generate_schedule(years: list[int], calendar: str) -> list[dict]:
    """Generate complete schedule for specified years."""
    all_records = []

    for year in years:
        url = CSV_URLS.get(year)
        if not url:
            print(f"⚠️  No URL configured for {year}, skipping")
            continue

        print(f"⬇️  Downloading {year} schedule...")
        try:
            csv_data = download_csv(url)
            records = parse_toronto_csv(csv_data, calendar)
            print(f"✅ Parsed {len(records)} weeks for {year}")
            all_records.extend(records)
        except Exception as e:
            print(f"❌ Failed to get {year}: {e}")

    # Sort by date
    def parse_date(r):
        try:
            return datetime.strptime(r['WeekStarting'], '%m/%d/%y')
        except:
            return datetime.min

    all_records.sort(key=parse_date)

    return all_records


def extrapolate_schedule(records: list[dict], end_year: int) -> list[dict]:
    """
    Extrapolate schedule into future years based on known patterns.

    Uses the last year's worth of data to determine:
    - Which week is garbage vs recycling (bi-weekly alternating)
    - Yard waste season (typically March-November)
    - Christmas tree weeks (early January)

    The pattern repeats with adjustments for which day of week the year starts on.
    """
    if not records:
        return records

    # Parse all dates and find the last date
    def parse_date(r):
        try:
            return datetime.strptime(r['WeekStarting'], '%m/%d/%y')
        except:
            return None

    dated_records = [(parse_date(r), r) for r in records]
    dated_records = [(d, r) for d, r in dated_records if d is not None]
    dated_records.sort(key=lambda x: x[0])

    if not dated_records:
        return records

    last_date, last_record = dated_records[-1]
    last_year = last_date.year

    if last_year >= end_year:
        print(f"📅 Schedule already extends to {last_year}, no extrapolation needed")
        return records

    print(f"\n🔮 Extrapolating schedule from {last_year} to {end_year}...")

    # Analyze the pattern from the last year of data
    # Find which weeks are garbage vs recycling
    last_year_records = [(d, r) for d, r in dated_records if d.year == last_year]

    # Determine the garbage/recycling alternation pattern
    # We'll use the last record to know if next week should be garbage or recycling
    last_was_garbage = last_record['Garbage'] == 'W'

    # Start from the week after the last known date
    current_date = last_date + timedelta(weeks=1)
    is_garbage_week = not last_was_garbage  # Alternate from last

    new_records = list(records)  # Copy existing

    while current_date.year <= end_year:
        month = current_date.month

        # Determine what's collected this week
        green_bin = 'W'  # Always collected
        garbage = 'W' if is_garbage_week else '0'
        recycling = '0' if is_garbage_week else 'W'

        # Yard waste: March through November (roughly)
        yard_waste = 'W' if (3 <= month <= 11) and is_garbage_week else '0'

        # Christmas trees: First two garbage weeks of January
        christmas_tree = '0'
        if month == 1 and is_garbage_week:
            # Check if this is one of the first two garbage weeks of January
            jan_start = datetime(current_date.year, 1, 1)
            weeks_into_jan = (current_date - jan_start).days // 7
            if weeks_into_jan < 4:  # First 4 weeks of January
                christmas_tree = 'W'

        new_records.append({
            'Calendar': 'Custom',
            'WeekStarting': current_date.strftime('%m/%d/%y'),
            'GreenBin': green_bin,
            'Garbage': garbage,
            'Recycling': recycling,
            'YardWaste': yard_waste,
            'ChristmasTree': christmas_tree,
        })

        # Move to next week and alternate
        current_date += timedelta(weeks=1)
        is_garbage_week = not is_garbage_week

    extrapolated_count = len(new_records) - len(records)
    print(f"✅ Added {extrapolated_count} extrapolated weeks through {end_year}")

    return new_records


def write_schedule(records: list[dict], output_path: Path):
    """Write schedule to CSV file."""
    fieldnames = ['Calendar', 'WeekStarting', 'GreenBin', 'Garbage', 'Recycling', 'YardWaste', 'ChristmasTree']

    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    print(f"✅ Wrote {len(records)} records to {output_path}")


def preview_schedule(records: list[dict], weeks: int = 8):
    """Show preview of upcoming schedule."""
    today = datetime.now()

    print(f"\n📅 Schedule Preview (next {weeks} weeks):")
    print("=" * 60)

    shown = 0
    for record in records:
        try:
            date = datetime.strptime(record['WeekStarting'], '%m/%d/%y')
        except:
            continue

        if date < today:
            continue

        if shown >= weeks:
            break

        items = []
        if record['GreenBin'] == 'W':
            items.append('🟢 Green')
        if record['Garbage'] == 'W':
            items.append('⬛ Garbage')
        if record['Recycling'] == 'W':
            items.append('♻️  Recycling')
        if record['YardWaste'] == 'W':
            items.append('🟤 Yard')
        if record['ChristmasTree'] == 'W':
            items.append('🎄 Tree')

        date_str = date.strftime('%a %b %d, %Y')
        print(f"{date_str}: {', '.join(items)}")
        shown += 1


def main():
    parser = argparse.ArgumentParser(description='Generate MMM-MyWastePickup schedule from Toronto Open Data')
    parser.add_argument('--write', action='store_true', help='Write to schedule_custom.csv')
    parser.add_argument('--years', nargs='+', type=int, default=[2025, 2026], help='Years to download from Toronto')
    parser.add_argument('--extend', type=int, default=None, help='Extrapolate schedule through this year (e.g., 2035)')
    parser.add_argument('--calendar', default=DEFAULT_CALENDAR, help='Toronto calendar (e.g., Wednesday1)')
    parser.add_argument('--output', type=Path, default=OUTPUT_FILE, help='Output file path')
    parser.add_argument('--preview', type=int, default=8, help='Number of weeks to preview')
    args = parser.parse_args()

    print(f"🗓️  Toronto Waste Schedule Generator")
    print(f"   Calendar: {args.calendar}")
    print(f"   Years to download: {args.years}")
    if args.extend:
        print(f"   Extrapolate through: {args.extend}")
    print()

    records = generate_schedule(args.years, args.calendar)

    if not records:
        print("❌ No schedule data found!")
        sys.exit(1)

    # Extrapolate into future if requested
    if args.extend:
        records = extrapolate_schedule(records, args.extend)

    preview_schedule(records, args.preview)

    if args.write:
        write_schedule(records, args.output)
        print(f"\n📝 To deploy to RPi:")
        print(f"   cd /Users/doug/Programming/dkSRC/apps/MagicMirror/modules/MMM-MyWastePickup")
        print(f"   git add schedule_custom.csv && git commit -m 'Update waste schedule' && git push")
        print(f"   ssh 192.168.20.18 'cd ~/MagicMirror/modules/MMM-MyWastePickup && git pull && pm2 restart mm'")
    else:
        print(f"\n💡 Run with --write to save to {args.output}")


if __name__ == "__main__":
    main()
