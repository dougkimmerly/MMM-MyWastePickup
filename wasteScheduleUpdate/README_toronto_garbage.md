# Toronto Garbage Collection Schedule Scripts

**Address:** 55 Tenth Street, South Etobicoke  
**District:** 1  
**Schedule:** Wednesday 1  

---

## Your Schedule

| Week Type | Dates (2026) | What to Put Out |
|-----------|--------------|-----------------|
| Garbage weeks | Jan 7, Jan 21, Feb 4, Feb 18... | 🗑️ Garbage + 🟢 Green Bin |
| Recycling weeks | Jan 14, Jan 28, Feb 11, Feb 25... | ♻️ Recycling + 🟢 Green Bin |

**Extras:**
- 🎄 Christmas Trees: Collected on garbage weeks in January (Jan 7, Jan 21)
- 🟤 Yard Waste: Collected on garbage weeks from mid-March to mid-December

---

## Scripts Included

### 1. `toronto_garbage_csv.py` (Recommended)
Human-friendly output with local caching.

```bash
# Show next 4 weeks
python toronto_garbage_csv.py

# Show just the next collection
python toronto_garbage_csv.py --next

# Force refresh the cached data
python toronto_garbage_csv.py --refresh
```

### 2. `toronto_garbage_json.py` (For n8n/Automation)
JSON output for workflows and home automation.

```bash
# Get next collection as JSON
python toronto_garbage_json.py

# Get all upcoming collections as JSON  
python toronto_garbage_json.py --all
```

Example output:
```json
{
  "calendar": "Wednesday 1",
  "next_collection_date": "2026-01-07",
  "days_until": 1,
  "collection_tomorrow": true,
  "items": ["Green Bin", "Garbage", "Christmas Tree"],
  "notification_message": "🗑️ Green Bin, Garbage, Christmas Tree collection TOMORROW!"
}
```

### 3. `toronto_garbage.py` (API Version)
Uses the Toronto Open Data API directly. Alternative if CSV version has issues.

---

## n8n Workflow Setup

### Daily Reminder Workflow
1. **Schedule Trigger**: Run every day at 6 PM (or whenever you want the reminder)
2. **Execute Command Node**: `python /path/to/toronto_garbage_json.py`
3. **IF Node**: Check `{{ $json.collection_tomorrow }} == true`
4. **Send Notification**: Email, Slack, Pushover, SMS, etc.

### Example n8n Expression for Message
```
{{ $json.notification_message }}
```

---

## Why You Were Off By a Week

Toronto announced that **for 2026, garbage and recycling weeks switched in some locations** (Districts 2 and 3). Your collection day stays the same (Wednesday), but the garbage vs recycling weeks may have swapped from what you were used to in 2025.

---

## Data Source

All data comes from the Toronto Open Data Portal:  
https://open.toronto.ca/dataset/solid-waste-pickup-schedule/

The scripts cache the CSV locally at `~/.toronto_garbage_cache/` and auto-refresh weekly.
