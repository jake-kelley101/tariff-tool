#!/usr/bin/env python3
"""
rebuild_232.py
--------------
Rebuilds data/sec232.b64 from a new Section 232 scope Excel file,
then injects it into index.html.

Usage:
    python scripts/rebuild_232.py path/to/Section_232_Scope.xlsx

The Excel file should have columns:
    HTS Chapter/Code | Description | Annex | Applies To | Tariff

Tariff values should be decimals (0.5 = 50%, 0.25 = 25%, 0.15 = 15%).
"""

import sys, re, json, gzip, base64
import pandas as pd
from pathlib import Path

REPO_ROOT  = Path(__file__).parent.parent
HTML_FILE  = REPO_ROOT / "index.html"
DATA_DIR   = REPO_ROOT / "data"
S232_FILE  = DATA_DIR / "sec232.b64"


def log(msg):
    print(f"[rebuild_232] {msg}", flush=True)


def build_s232(xlsx_path):
    df = pd.read_excel(xlsx_path, dtype=str)
    log(f"Loaded {len(df)} rows from {xlsx_path}")

    lookup = {}
    for _, row in df.iterrows():
        code = re.sub(r'\D', '', str(row.get('HTS Chapter/Code', '')).strip())
        if not code or len(code) < 4:
            continue
        try:
            rate = float(row['Tariff']) * 100
        except (ValueError, TypeError):
            continue
        applies = str(row.get('Applies To', '')).strip()
        applies = None if applies.lower() in ('nan', '', 'none') else applies

        if code not in lookup:
            lookup[code] = {'r': rate, 'a': set()}
        else:
            # Keep lowest rate for duplicates
            lookup[code]['r'] = min(lookup[code]['r'], rate)

        if applies:
            lookup[code]['a'].add(applies)

    # Convert sets to sorted lists
    final = {k: {'r': v['r'], 'a': sorted(v['a'])} for k, v in lookup.items()}
    log(f"Built {len(final)} unique entries")

    from collections import Counter
    rate_dist = Counter(v['r'] for v in final.values())
    log(f"Rate distribution: { {f'{k:.0f}%': v for k,v in sorted(rate_dist.items())} }")

    return final


def save_and_inject(data):
    j = json.dumps(data, separators=(',', ':'))
    compressed = gzip.compress(j.encode())
    b64 = base64.b64encode(compressed).decode()

    S232_FILE.write_text(b64)
    log(f"Saved data/sec232.b64 ({len(b64)/1024:.1f} KB)")

    html = HTML_FILE.read_text(encoding='utf-8')
    pattern = r'(const S232_B64\s*=\s*")[^"]+(")'
    new_html, count = re.subn(pattern, lambda m: m.group(1) + b64 + m.group(2), html)
    if count == 0:
        log("ERROR: Could not find S232_B64 in index.html")
        sys.exit(1)
    HTML_FILE.write_text(new_html, encoding='utf-8')
    log("Injected into index.html ✓")


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/rebuild_232.py path/to/Section_232_Scope.xlsx")
        sys.exit(1)

    xlsx_path = Path(sys.argv[1])
    if not xlsx_path.exists():
        log(f"ERROR: File not found: {xlsx_path}")
        sys.exit(1)

    data = build_s232(xlsx_path)
    save_and_inject(data)
    log("Done. Commit with: git add data/sec232.b64 index.html && git commit -m 'Update §232 scope'")


if __name__ == '__main__':
    main()
