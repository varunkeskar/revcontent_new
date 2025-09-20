#!/usr/bin/env python3
"""
Toggle Revcontent campaigns ON/OFF.
- Mode "auto" turns campaigns ON between 09:00 and 23:59 local NY time, OFF otherwise.
- You can also force "on" or "off".
Reads:
  ACCESS_TOKEN   -> Revcontent API token  (required)
  CAMPAIGN_IDS   -> comma/space list like: 2453224,2448613 (required if not passed via --campaigns)
  API_URL        -> optional, defaults to official endpoint
"""

from __future__ import annotations
import argparse, os, sys, json, datetime, requests

# zoneinfo works on Python 3.9+; tzdata (pip) provides the database in containers
from zoneinfo import ZoneInfo

API_DEFAULT = "https://api.revcontent.io/stats/api/v1.0/boosts"

def now_in_tz(tzname: str) -> datetime.datetime:
    return datetime.datetime.now(ZoneInfo(tzname))

def should_be_on(start_hour: int, end_hour_exclusive: int, tzname: str) -> bool:
    """
    Return True if current local hour in tz is within [start_hour, end_hour_exclusive).
    Example: start=9, end=24 => 09:00 through 23:59.
    """
    h = now_in_tz(tzname).hour
    return start_hour <= h < end_hour_exclusive

def parse_campaigns(raw: str | None) -> list[int]:
    if not raw:
        return []
    items = []
    for tok in raw.replace(",", " ").split():
        items.append(int(tok))
    return items

def toggle(session: requests.Session, token: str, campaign_id: int, enabled: bool, api_url: str) -> tuple[int, str]:
    payload = {"id": str(campaign_id), "enabled": "on" if enabled else "off"}
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    r = session.post(api_url, headers=headers, json=payload, timeout=30)
    return r.status_code, r.text

def main() -> int:
    p = argparse.ArgumentParser(description="Toggle Revcontent campaigns.")
    p.add_argument("--campaigns", nargs="*", type=int,
                   help="Campaign IDs (space separated). If omitted, uses CAMPAIGN_IDS env.")
    p.add_argument("--enabled", choices=["on","off","auto"], default="auto",
                   help='on/off or "auto" to follow 9–23:59 America/New_York window.')
    p.add_argument("--start", type=int, default=9, help="Start hour local NY time (default 9).")
    p.add_argument("--end", type=int, default=24, help="End hour (exclusive) local NY time (default 24).")
    p.add_argument("--timezone", default="America/New_York", help='IANA TZ (default "America/New_York").')
    p.add_argument("--api-url", default=os.getenv("API_URL", API_DEFAULT))
    p.add_argument("--dry-run", action="store_true", help="Print actions, don’t call the API.")
    args = p.parse_args()

    token = os.getenv("ACCESS_TOKEN")
    if not token:
        print("ERROR: ACCESS_TOKEN env var is required.", file=sys.stderr)
        return 2

    campaigns = args.campaigns or parse_campaigns(os.getenv("CAMPAIGN_IDS"))
    if not campaigns:
        print("ERROR: Provide campaign IDs via --campaigns or CAMPAIGN_IDS env.", file=sys.stderr)
        return 2

    if args.enabled == "auto":
        enabled = should_be_on(args.start, args.end, args.timezone)
    else:
        enabled = (args.enabled == "on")

    now_utc = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M:%S")
    print(f"=== Revcontent toggle @ {now_utc}Z ===")
    print(f"TZ window {args.start}:00–{args.end-1}:59 in {args.timezone} | enabled => {'ON' if enabled else 'OFF'}")
    print(f"Campaigns: {campaigns}\n")

    if args.dry_run:
        print("[dry-run] No API calls made.")
        return 0

    with requests.Session() as s:
        for cid in campaigns:
            code, body = toggle(s, token, cid, enabled, args.api_url)
            print(f"Campaign {cid}: HTTP {code}")
            print(f"Response: {body}\n")

    print("=== Done ===")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())