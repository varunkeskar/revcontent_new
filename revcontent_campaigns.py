#!/usr/bin/env python3
import os
import sys
import json
import argparse
import datetime
from zoneinfo import ZoneInfo   # Python 3.9+
import requests

# ======= CONFIG =======
API_URL   = "https://api.revcontent.io/stats/api/v1.0/boosts"

# If your account uses a different token endpoint, change TOKEN_URL or set env TOKEN_URL.
TOKEN_URL = os.environ.get("TOKEN_URL", "https://api.revcontent.io/oauth/token")

# Campaign IDs: env CAMPAIGN_IDS like "2453224,2448613" or fallback list below.
DEFAULT_CAMPAIGNS = [2453224, 2448613]
# ======================

def parse_args():
    p = argparse.ArgumentParser(description="Toggle Revcontent campaign status.")
    p.add_argument("--enabled", choices=["auto", "on", "off"], default="auto",
                   help="auto = 9:00–23:59 America/New_York => ON, otherwise OFF")
    p.add_argument("--dry-run", action="store_true", help="Print actions; do not call API.")
    return p.parse_args()

def campaigns_from_env():
    raw = os.environ.get("CAMPAIGN_IDS", "")
    if raw.strip():
        try:
            return [int(x.strip()) for x in raw.split(",") if x.strip()]
        except ValueError:
            print("WARN: CAMPAIGN_IDS not parseable; using defaults.", file=sys.stderr)
    return DEFAULT_CAMPAIGNS

def resolve_enabled(mode: str) -> str:
    if mode in ("on", "off"):
        return mode
    # auto: 9:00–23:59 in America/New_York -> on, else off
    now_local = datetime.datetime.now(ZoneInfo("America/New_York"))
    enabled = "on" if (now_local.hour >= 9 and now_local.hour <= 23) else "off"
    return enabled

def get_access_token() -> str:
    # 1) if ACCESS_TOKEN is provided, just use it
    env_token = os.environ.get("ACCESS_TOKEN")
    if env_token:
        return env_token

    # 2) otherwise fetch one with client credentials
    client_id = os.environ.get("CLIENT_ID")
    client_secret = os.environ.get("CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError(
            "Missing CLIENT_ID/CLIENT_SECRET. Set them as environment variables."
        )

    # Standard OAuth2 client-credentials
    data = {"grant_type": "client_credentials"}
    resp = requests.post(TOKEN_URL, data=data, auth=(client_id, client_secret), timeout=30)

    if resp.status_code != 200:
        raise RuntimeError(
            f"Token request failed {resp.status_code}: {resp.text[:300]}"
        )

    payload = resp.json()
    token = payload.get("access_token")
    if not token:
        raise RuntimeError(f"No access_token in token response: {payload}")
    return token

def main():
    args = parse_args()
    campaigns = campaigns_from_env()
    enabled = resolve_enabled(args.enabled)
    now_utc = datetime.datetime.now(ZoneInfo("UTC")).strftime("%Y-%m-%d %H:%M:%S")

    print(f"=== Revcontent toggle @ {now_utc}Z ===")
    print("TZ window 9:00–23:59 in America/New_York | enabled =>", enabled.upper())
    print("Campaigns:", campaigns)
    print()

    if args.dry_run:
        print("[dry-run] No API calls made.")
        return

    try:
        token = get_access_token()
    except Exception as e:
        print(f"ERROR retrieving access token: {e}", file=sys.stderr)
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    desired = "on" if enabled == "on" else "off"

    for cid in campaigns:
        body = {"id": cid, "enabled": desired}
        try:
            r = requests.post(API_URL, headers=headers, json=body, timeout=30)
            print(f"Campaign {cid}: HTTP {r.status_code}")
            print("Response:", r.text)
            print()
        except Exception as e:
            print(f"Campaign {cid}: request failed: {e}", file=sys.stderr)
            print()

    print("=== Done ===")

if __name__ == "__main__":
    main()
