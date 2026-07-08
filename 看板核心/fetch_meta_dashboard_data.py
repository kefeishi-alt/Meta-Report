#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


SHANGHAI = timezone(timedelta(hours=8))
CORE_DIR = Path(__file__).resolve().parent
ROOT_DIR = CORE_DIR.parent
SYNC_ROOT = ROOT_DIR.parent / "Ruitang Sync"
ENV_PATH = SYNC_ROOT / ".env.meta"
OUTPUT_JSON = CORE_DIR / "meta-dashboard-data.json"

ACCOUNT_REGION_MAP = {
    "act_1153764569041892": "CA",
    "act_833690491599339": "US",
    "act_834730654689701": "US",
    "act_943180600302699": "US",
    "act_23950483557887608": "UK",
    "act_1020127240037485": "EU",
}


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip().strip("'").strip('"')


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"Missing required env var: {name}")
    return value


def resolve_account_ids() -> list[str]:
    raw = os.getenv("META_AD_ACCOUNT_IDS", "").strip()
    if not raw:
        return list(ACCOUNT_REGION_MAP.keys())
    return [x.strip() for x in raw.split(",") if x.strip()]


def graph_json(url: str, *, attempts: int = 4) -> dict:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(url, timeout=90) as response:
                return json.loads(response.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code not in {429, 500, 502, 503, 504} or attempt == attempts:
                raise
        except urllib.error.URLError as exc:
            last_error = exc
            if attempt == attempts:
                raise
        time.sleep(2 ** attempt)
    raise RuntimeError(f"Meta API request failed after retries: {last_error}")


def iter_insights(account_id: str, since: str, until: str) -> list[dict]:
    params = {
        "level": "ad",
        "time_increment": "1",
        "limit": "500",
        "fields": ",".join([
            "account_name",
            "ad_id",
            "ad_name",
            "date_start",
            "date_stop",
            "spend",
            "impressions",
            "cpm",
            "ctr",
            "cpc",
            "actions",
            "action_values",
            "cost_per_action_type",
        ]),
        "time_range": json.dumps({"since": since, "until": until}, ensure_ascii=False),
        "access_token": require_env("META_ACCESS_TOKEN"),
    }
    url = f"https://graph.facebook.com/v23.0/{account_id}/insights?{urllib.parse.urlencode(params)}"
    rows: list[dict] = []
    while url:
        payload = graph_json(url)
        rows.extend(payload.get("data", []))
        url = payload.get("paging", {}).get("next")
    return rows


def action_metric(items: list[dict] | None, action_type: str) -> float:
    for item in items or []:
        if item.get("action_type") == action_type:
            try:
                return float(item.get("value") or 0)
            except (TypeError, ValueError):
                return 0.0
    return 0.0


def build_row(account_id: str, item: dict) -> dict:
    spend = float(item.get("spend") or 0.0)
    impressions = float(item.get("impressions") or 0.0)
    purchases = action_metric(item.get("actions"), "purchase")
    revenue = action_metric(item.get("action_values"), "purchase")
    clicks = action_metric(item.get("actions"), "link_click")
    add_to_cart = action_metric(item.get("actions"), "add_to_cart")
    checkouts = action_metric(item.get("actions"), "initiate_checkout")
    cpm = float(item.get("cpm") or 0.0) if item.get("cpm") not in (None, "") else None
    ctr = (clicks / impressions) if impressions else 0.0
    cpc = (spend / clicks) if clicks else None
    cpp = action_metric(item.get("cost_per_action_type"), "purchase") or ((spend / purchases) if purchases else None)
    aov = (revenue / purchases) if purchases else None
    conversion_rate = (purchases / clicks) if clicks else 0.0
    add_to_cart_rate = (add_to_cart / clicks) if clicks else 0.0
    ic_rate = (checkouts / clicks) if clicks else 0.0
    roi = (revenue / spend) if spend else None

    return {
        "region": ACCOUNT_REGION_MAP.get(account_id, "US"),
        "accountName": item.get("account_name", ""),
        "adId": item.get("ad_id", ""),
        "day": item.get("date_start", ""),
        "ads": item.get("ad_name", ""),
        "spend": round(spend, 2),
        "revenue": round(revenue, 2),
        "roi": round(roi, 4) if roi is not None else None,
        "purchases": round(purchases, 4),
        "conversionRate": round(conversion_rate, 4),
        "cpp": round(cpp, 2) if cpp is not None else None,
        "aov": round(aov, 2) if aov is not None else None,
        "impressions": int(impressions),
        "clicks": round(clicks, 4),
        "cpm": round(cpm, 2) if cpm is not None else None,
        "ctr": round(ctr, 4),
        "cpc": round(cpc, 2) if cpc is not None else None,
        "addToCart": round(add_to_cart, 4),
        "checkouts": round(checkouts, 4),
        "addToCartRate": round(add_to_cart_rate, 4),
        "icRate": round(ic_rate, 4),
        "start": item.get("date_start", ""),
        "end": item.get("date_stop", item.get("date_start", "")),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch Mooncool Meta dashboard data from the Meta API.")
    parser.add_argument("--start-date", help="Start date in YYYY-MM-DD.")
    parser.add_argument("--end-date", help="End date in YYYY-MM-DD.")
    parser.add_argument("--lookback-days", type=int, default=7, help="Refresh window when dates are omitted. Default: 7.")
    parser.add_argument("--bootstrap-lookback-days", type=int, default=180, help="Initial fetch window when no cached JSON exists. Default: 180.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and print summary only.")
    return parser.parse_args()


def resolve_dates(args: argparse.Namespace) -> tuple[str, str]:
    if args.start_date and args.end_date:
        return args.start_date, args.end_date
    if args.start_date or args.end_date:
        raise SystemExit("Both --start-date and --end-date are required together.")
    end = datetime.now(SHANGHAI).date()
    lookback = args.bootstrap_lookback_days if not OUTPUT_JSON.exists() else args.lookback_days
    start = end - timedelta(days=max(lookback - 1, 0))
    return start.isoformat(), end.isoformat()


def load_existing_rows() -> list[dict]:
    if not OUTPUT_JSON.exists():
        return []
    payload = json.loads(OUTPUT_JSON.read_text(encoding="utf-8"))
    rows = payload.get("rows", []) if isinstance(payload, dict) else payload
    return rows if isinstance(rows, list) else []


def existing_rows_for_account(existing_rows: list[dict], account_id: str, since: str, until: str) -> list[dict]:
    region = ACCOUNT_REGION_MAP.get(account_id, "US")
    return [
        row for row in existing_rows
        if row.get("region") == region and since <= row.get("day", "") <= until
    ]


def row_key(row: dict) -> tuple[str, str, str, str, str]:
    return (
        row.get("day", ""),
        row.get("region", ""),
        row.get("accountName", ""),
        row.get("adId", ""),
        row.get("ads", ""),
    )


def merge_rows(existing_rows: list[dict], fresh_rows: list[dict], since: str, until: str) -> list[dict]:
    merged: dict[tuple[str, str, str, str, str], dict] = {}
    for row in existing_rows:
        day = row.get("day", "")
        if since <= day <= until:
            continue
        merged[row_key(row)] = row
    for row in fresh_rows:
        merged[row_key(row)] = row
    return sorted(merged.values(), key=lambda item: (item["day"], item["region"], item["accountName"], item["ads"]))


def main() -> None:
    args = parse_args()
    load_env(ENV_PATH)
    since, until = resolve_dates(args)

    account_ids = resolve_account_ids()
    existing_rows = load_existing_rows()
    fetched_rows: list[dict] = []
    failed_accounts: list[str] = []
    for account_id in account_ids:
        try:
            fetched_rows.extend(build_row(account_id, item) for item in iter_insights(account_id, since, until))
        except Exception as exc:
            cached_rows = existing_rows_for_account(existing_rows, account_id, since, until)
            if not cached_rows:
                raise RuntimeError(f"Meta API failed for {account_id} and no cached rows are available.") from exc
            failed_accounts.append(account_id)
            fetched_rows.extend(cached_rows)

    rows = merge_rows(existing_rows, fetched_rows, since, until)
    payload = {
        "generatedAt": datetime.now(SHANGHAI).isoformat(),
        "startDate": since,
        "endDate": until,
        "warnings": [f"Used cached rows for {account_id} after Meta API failure." for account_id in failed_accounts],
        "rows": rows,
    }

    if args.dry_run:
        print(json.dumps({
            "startDate": since,
            "endDate": until,
            "rowCount": len(fetched_rows),
            "mergedRowCount": len(rows),
            "failedAccounts": failed_accounts,
            "regions": sorted({row["region"] for row in rows}),
        }, ensure_ascii=False, indent=2))
        return

    OUTPUT_JSON.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(f"Fetched {len(rows)} rows into {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
