#!/usr/bin/env python3
"""
Toronto Garbage Schedule - JSON Output for n8n/Automation

Returns JSON output suitable for n8n workflows, Home Assistant, etc.

Usage:
    python toronto_garbage_json.py              # JSON for next collection
    python toronto_garbage_json.py --all        # JSON for all upcoming
    
Example n8n setup:
1. Schedule Trigger: Run every day at 6 PM
2. Execute Command: python /path/to/toronto_garbage_json.py
3. IF node: Check if collection_tomorrow is true
4. Send notification (email, Slack, etc.)
"""

import csv
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

# ============================================================
# CONFIGURATION
# ============================================================
CALENDAR = "Wednesday2"  # 55 Tenth Street, South Etobicoke
ADDRESS = "55 Tenth Street, South Etobicoke"
# ============================================================

CSV_URLS = {
    2025: "https://ckan0.cf.opendata.inter.prod-toronto.ca/dataset/7b70189a-aede-42f1-b092-8708fa4f5fc3/resource/d78c77fe-6055-44d1-836b-e2d36722b3ce/download/pickup-schedule-2025.csv",
    2026: "https://ckan0.cf.opendata.inter.prod-toronto.ca/dataset/7b70189a-aede-42f1-b092-8708fa4f5fc3/resource/fe6f168c-4d5e-4b62-856b-3306a0fe56dd/download/pickup-schedule-2026.csv",
}

CACHE_DIR = Path.home() / ".toronto_garbage_cache"


def ensure_cache():
    CACHE_DIR.mkdir(exist_ok=True)


def download_if_needed(year: int) -> Path:
    ensure_cache()
    cache_path = CACHE_DIR / f"pickup-schedule-{year}.csv"
    
    # Refresh weekly
    if cache_path.exists():
        age = datetime.now() - datetime.fromtimestamp(cache_path.stat().st_mtime)
        if age.days < 7:
            return cache_path
    
    url = CSV_URLS.get(year)
    if not url:
        return cache_path if cache_path.exists() else None
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Toronto-Garbage/1.0'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            cache_path.write_bytes(resp.read())
    except Exception:
        pass  # Use cache if download fails
    
    return cache_path if cache_path.exists() else None


def load_records(year: int) -> list[dict]:
    csv_path = download_if_needed(year)
    if not csv_path:
        return []
    
    records = []
    with open(csv_path, 'r') as f:
        for row in csv.DictReader(f):
            if row.get('Calendar') == CALENDAR:
                try:
                    records.append({
                        'date': datetime.strptime(row['WeekStarting'], '%Y-%m-%d'),
                        'green_bin': row.get('GreenBin', '0') not in ['0', ''],
                        'garbage': row.get('Garbage', '0') not in ['0', ''],
                        'recycling': row.get('Recycling', '0') not in ['0', ''],
                        'yard_waste': row.get('YardWaste', '0') not in ['0', ''],
                        'christmas_tree': row.get('ChristmasTree', '0') not in ['0', ''],
                    })
                except ValueError:
                    continue
    return records


def get_next_collection() -> dict:
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)
    
    # Load current year and next if needed
    records = load_records(today.year)
    if today.month >= 11:
        records.extend(load_records(today.year + 1))
    
    records.sort(key=lambda x: x['date'])
    
    for r in records:
        if r['date'] >= today and any([r['green_bin'], r['garbage'], r['recycling']]):
            items = []
            if r['green_bin']:
                items.append("Green Bin")
            if r['garbage']:
                items.append("Garbage")
            if r['recycling']:
                items.append("Recycling")
            if r['yard_waste']:
                items.append("Yard Waste")
            if r['christmas_tree']:
                items.append("Christmas Tree")
            
            days_until = (r['date'] - today).days
            
            return {
                "calendar": CALENDAR,
                "address": ADDRESS,
                "next_collection_date": r['date'].strftime('%Y-%m-%d'),
                "next_collection_day": r['date'].strftime('%A'),
                "next_collection_formatted": r['date'].strftime('%A, %B %d, %Y'),
                "days_until": days_until,
                "collection_today": days_until == 0,
                "collection_tomorrow": days_until == 1,
                "items": items,
                "items_text": ", ".join(items),
                "is_garbage_week": r['garbage'],
                "is_recycling_week": r['recycling'],
                "notification_message": f"{'🗑️ ' if r['garbage'] else '♻️ '}{', '.join(items)} collection {'TODAY' if days_until == 0 else 'TOMORROW' if days_until == 1 else 'on ' + r['date'].strftime('%A')}!",
                "timestamp": datetime.now().isoformat(),
            }
    
    return {"error": "No upcoming collection found"}


def get_all_upcoming(weeks: int = 4) -> list[dict]:
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = today + timedelta(weeks=weeks)
    
    records = load_records(today.year)
    if end_date.year > today.year:
        records.extend(load_records(end_date.year))
    
    results = []
    for r in records:
        if today <= r['date'] <= end_date:
            items = []
            if r['green_bin']:
                items.append("Green Bin")
            if r['garbage']:
                items.append("Garbage")
            if r['recycling']:
                items.append("Recycling")
            if r['yard_waste']:
                items.append("Yard Waste")
            if r['christmas_tree']:
                items.append("Christmas Tree")
            
            if items:
                results.append({
                    "date": r['date'].strftime('%Y-%m-%d'),
                    "day": r['date'].strftime('%A'),
                    "items": items,
                    "is_garbage_week": r['garbage'],
                    "is_recycling_week": r['recycling'],
                })
    
    results.sort(key=lambda x: x['date'])
    return {"calendar": CALENDAR, "address": ADDRESS, "collections": results}


if __name__ == "__main__":
    if "--all" in sys.argv:
        print(json.dumps(get_all_upcoming(), indent=2))
    else:
        print(json.dumps(get_next_collection(), indent=2))
