#!/usr/bin/env python3
import argparse
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

CORE_DIR = Path(__file__).resolve().parent
ROOT_DIR = CORE_DIR.parent
SOURCE_XLSX = ROOT_DIR / "看板-skf.xlsx"
SOURCE_JSON = CORE_DIR / "meta-dashboard-data.json"
TEMPLATE_HTML = CORE_DIR / "meta-dashboard-template.html"
OUTPUT_HTML = ROOT_DIR / "index.html"


def col_idx(col):
    n = 0
    for ch in col:
        n = n * 26 + (ord(ch) - 64)
    return n


def load_sheet_rows(xlsx_path, sheet_name='sheet1.xml'):
    with zipfile.ZipFile(xlsx_path) as z:
        shared = None
        if 'xl/sharedStrings.xml' in z.namelist():
            shared_xml = z.read('xl/sharedStrings.xml')
            root = ET.fromstring(shared_xml)
            ns = {'a': root.tag.split('}')[0].strip('{')}
            shared = []
            for si in root.findall('a:si', ns):
                texts = [t.text or '' for t in si.findall('.//a:t', ns)]
                shared.append(''.join(texts))
        sheet_xml = z.read(f'xl/worksheets/{sheet_name}')
    root = ET.fromstring(sheet_xml)
    ns = {'a': root.tag.split('}')[0].strip('{')}
    rows = []
    for row in root.findall('.//a:sheetData/a:row', ns):
        cells = row.findall('a:c', ns)
        if not cells:
            continue
        max_idx = max(col_idx(''.join(ch for ch in c.attrib.get('r', '') if ch.isalpha())) for c in cells)
        vals = [''] * max_idx
        for c in cells:
            col = ''.join(ch for ch in c.attrib.get('r', '') if ch.isalpha())
            idx = col_idx(col) - 1
            t = c.attrib.get('t')
            if t == 's':
                v = c.find('a:v', ns)
                vals[idx] = shared[int(v.text)] if v is not None else ''
            elif t == 'inlineStr':
                v = c.find('a:is/a:t', ns)
                vals[idx] = v.text if v is not None else ''
            else:
                v = c.find('a:v', ns)
                vals[idx] = v.text if v is not None else ''
        rows.append(vals)
    return rows


def load_json_rows(json_path):
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        rows = payload.get("rows", [])
    elif isinstance(payload, list):
        rows = payload
    else:
        rows = []
    if not isinstance(rows, list):
        raise SystemExit(f"Invalid JSON rows payload in {json_path}")
    return rows


def num(s):
    if s is None:
        return None
    s = str(s).strip()
    if s == '':
        return None
    s = s.replace(',', '').replace('$', '')
    if s.endswith('%'):
        try:
            return float(s[:-1]) / 100.0
        except Exception:
            return None
    try:
        return float(s)
    except Exception:
        return None


def map_region(account_name):
    a = (account_name or '').upper()
    if 'CA' in a:
        return 'CA'
    if 'UK' in a:
        return 'UK'
    if 'EU' in a:
        return 'EU'
    return 'US'


def parse_xlsx_rows():
    rows = load_sheet_rows(SOURCE_XLSX, 'sheet1.xml')
    headers = rows[0]
    out = []
    for r in rows[1:]:
        d = {headers[i]: r[i] if i < len(r) else '' for i in range(len(headers))}
        day = d.get('Day')
        if not day:
            continue
        out.append({
            'region': map_region(d.get('Account name', '')),
            'accountName': d.get('Account name', ''),
            'day': day,
            'ads': d.get('Ad name', ''),
            'spend': num(d.get('Amount spent (USD)')),
            'revenue': num(d.get('Purchases conversion value')),
            'roi': num(d.get('ROI')),
            'purchases': num(d.get('Purchases')),
            'conversionRate': num(d.get('Conversion Rate')),
            'cpp': num(d.get('Cost per purchase')),
            'aov': num(d.get('Average transaction value (USD)')),
            'impressions': num(d.get('Impressions')),
            'clicks': num(d.get('Link clicks')),
            'cpm': num(d.get('CPM (cost per 1,000 impressions)')),
            'ctr': num(d.get('CTR (link click-through rate)')),
            'cpc': num(d.get('CPC (cost per link click)')),
            'addToCart': num(d.get('Adds to cart')),
            'checkouts': num(d.get('Checkouts initiated')),
            'addToCartRate': num(d.get('Adds to cart Rate')),
            'icRate': num(d.get('IC Rate')),
            'start': d.get('Reporting starts'),
            'end': d.get('Reporting ends'),
        })
    return out


def parse_json_rows():
    rows = load_json_rows(SOURCE_JSON)
    out = []
    for row in rows:
        day = row.get("day")
        if not day:
            continue
        out.append({
            "region": row.get("region", "US"),
            "accountName": row.get("accountName", ""),
            "day": day,
            "ads": row.get("ads", ""),
            "spend": num(row.get("spend")),
            "revenue": num(row.get("revenue")),
            "roi": num(row.get("roi")),
            "purchases": num(row.get("purchases")),
            "conversionRate": num(row.get("conversionRate")),
            "cpp": num(row.get("cpp")),
            "aov": num(row.get("aov")),
            "impressions": num(row.get("impressions")),
            "clicks": num(row.get("clicks")),
            "cpm": num(row.get("cpm")),
            "ctr": num(row.get("ctr")),
            "cpc": num(row.get("cpc")),
            "addToCart": num(row.get("addToCart")),
            "checkouts": num(row.get("checkouts")),
            "addToCartRate": num(row.get("addToCartRate")),
            "icRate": num(row.get("icRate")),
            "start": row.get("start", day),
            "end": row.get("end", day),
        })
    return out


def aggregate_meta(creative_rows):
    by_day = {}
    for r in creative_rows:
        day = r['day']
        if day not in by_day:
            by_day[day] = {'date': day, 'spend': 0, 'revenue': 0, 'purchases': 0, 'impressions': 0, 'clicks': 0}
        by_day[day]['spend'] += r['spend'] or 0
        by_day[day]['revenue'] += r['revenue'] or 0
        by_day[day]['purchases'] += r['purchases'] or 0
        by_day[day]['impressions'] += r['impressions'] or 0
        by_day[day]['clicks'] += r['clicks'] or 0
    meta = []
    for day in sorted(by_day.keys()):
        v = by_day[day]
        spend = v['spend']; revenue = v['revenue']; purchases = v['purchases']; impressions = v['impressions']; clicks = v['clicks']
        def safe_div(a, b):
            return a / b if b else None
        meta.append({
            'date': day,
            'spend': spend,
            'revenue': revenue,
            'purchases': purchases,
            'impressions': impressions,
            'clicks': clicks,
            'conversionRate': safe_div(purchases, clicks),
            'roas': safe_div(revenue, spend),
            'cpa': safe_div(spend, purchases),
            'cpm': safe_div(spend, impressions) * 1000 if impressions else None,
            'ctr': safe_div(clicks, impressions),
            'cpc': safe_div(spend, clicks),
        })
    return meta


def parse_args():
    parser = argparse.ArgumentParser(description="Generate Mooncool dashboard HTML.")
    parser.add_argument("--source", choices=["auto", "xlsx", "json"], default="auto")
    return parser.parse_args()


def resolve_rows(source_mode):
    if source_mode == "json":
        if not SOURCE_JSON.exists():
            raise SystemExit(f"Missing {SOURCE_JSON}")
        return parse_json_rows()
    if source_mode == "xlsx":
        if not SOURCE_XLSX.exists():
            raise SystemExit(f"Missing {SOURCE_XLSX}")
        return parse_xlsx_rows()
    if SOURCE_JSON.exists():
        return parse_json_rows()
    if SOURCE_XLSX.exists():
        return parse_xlsx_rows()
    raise SystemExit(f"Missing both {SOURCE_JSON} and {SOURCE_XLSX}")


def main():
    args = parse_args()
    if not TEMPLATE_HTML.exists():
        raise SystemExit(f'Missing {TEMPLATE_HTML}')
    rows = resolve_rows(args.source)
    if not rows:
        raise SystemExit('No rows found.')
    all_data = {}
    for region in ['US', 'CA', 'UK', 'EU']:
        creative = [r for r in rows if r['region'] == region]
        all_data[region] = {'creative': creative, 'meta': aggregate_meta(creative)}
    text = TEMPLATE_HTML.read_text(encoding='utf-8')
    text = text.replace('__ALL_DATA__', json.dumps(all_data, ensure_ascii=False))
    if OUTPUT_HTML.name == TEMPLATE_HTML.name:
        raise SystemExit('Refusing to overwrite template file.')
    OUTPUT_HTML.write_text(text, encoding='utf-8')
    print(f'Generated {OUTPUT_HTML}')


if __name__ == '__main__':
    main()
