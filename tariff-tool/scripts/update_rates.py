#!/usr/bin/env python3
"""
update_rates.py
---------------
Downloads the latest USITC Harmonized Tariff Schedule JSON and rebuilds
the base_rates.b64 data blob embedded in index.html.

Run automatically by GitHub Actions every week, or manually:
    python scripts/update_rates.py

Environment variables (optional — set in GitHub Actions workflow):
    SEC122_RATE   Additional tariff rate under Section 122 (default: 10)
    SEC301_RATE   Additional tariff rate under Section 301 (default: 25)
"""

import json, gzip, base64, re, sys, os, urllib.request, urllib.error
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────
REPO_ROOT   = Path(__file__).parent.parent
HTML_FILE   = REPO_ROOT / "index.html"
DATA_DIR    = REPO_ROOT / "data"
RATES_FILE  = DATA_DIR / "base_rates.b64"

# ── USITC HTS download URL ─────────────────────────────────────────────────
# USITC publishes the current HTS as a JSON file. The URL changes per revision;
# we try the latest known URL and fall back to the download index page pattern.
USITC_URLS = [
    "https://hts.usitc.gov/reststop/api/details/export?format=json",
    "https://hts.usitc.gov/reststop/api/export?format=json",
]

# ── Supplemental rates for chapters not in USITC download ─────────────────
# Chapters 1-39 are sometimes excluded from the USITC export.
# These heading-level rates are from the 2025 HTSUS and change rarely.
SUPPLEMENTAL = {
    '15': 3.2, '25': 0.0, '27': 0.0, '28': 3.7, '29': 3.7,
    '32': 3.7, '3203': 3.1, '3204': 6.5, '3208': 3.7, '3209': 3.2,
    '3214': 3.5,
    '34': 3.7, '3402': 4.0,
    '35': 2.1, '3506': 2.1,
    '38': 3.7, '3810': 3.7,
    '39': 5.3, '3901': 3.7, '3902': 3.7, '3903': 3.7, '3904': 3.7,
    '3906': 4.2, '3907': 4.2, '3908': 6.5, '3909': 3.7, '3910': 3.7,
    '3916': 5.8, '3917': 3.8, '3918': 5.3, '3919': 5.3, '3920': 4.2,
    '3921': 4.2, '3922': 3.3, '3923': 3.0, '3924': 3.4, '3925': 5.3,
    '3926': 5.3,
}


def log(msg):
    print(f"[update_rates] {msg}", flush=True)


def parse_av(raw):
    """Extract ad valorem % from a rate string like '5%', 'Free', '3.7% + $0.02/kg'."""
    if not raw:
        return None
    s = str(raw).strip()
    if s.lower() == 'free':
        return 0.0
    m = re.search(r'([\d.]+)\s*%', s)
    return float(m.group(1)) if m else None


def is_compound(raw):
    """True if rate has both an ad valorem % and a specific component."""
    if not raw:
        return False
    s = str(raw).strip()
    has_pct = bool(re.search(r'[\d.]+\s*%', s))
    has_specific = bool(re.search(r'\$[\d.]|\d+\.*\d*¢', s))
    return has_pct and has_specific


def download_hts_json():
    """Download the USITC HTS JSON, trying each known URL."""
    for url in USITC_URLS:
        try:
            log(f"Trying {url} ...")
            req = urllib.request.Request(url, headers={'User-Agent': 'tariff-tool/1.0'})
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                log(f"Downloaded {len(data)} HTS entries")
                return data
        except Exception as e:
            log(f"  Failed: {e}")
    return None


def build_rate_lookup(hts_data):
    """Build {hts8_digits: {r, raw, c}} lookup from USITC data."""
    lookup = {}
    if hts_data:
        for entry in hts_data:
            htsno = entry.get('htsno', '')
            general = entry.get('general', '')
            if not htsno or not general:
                continue
            key = re.sub(r'\D', '', htsno)
            rate = parse_av(general)
            if rate is not None and key not in lookup:
                lookup[key] = {
                    'r': rate,
                    'raw': general,
                    'c': is_compound(general)
                }
        log(f"Parsed {len(lookup)} rates from USITC data")

    # Load existing rates to find which HTS codes the tool uses
    existing = load_existing_rates()

    # Fill any gaps with supplemental table
    filled = 0
    for code in list(existing.keys()):
        if code not in lookup:
            for length in range(min(len(code), 8), 1, -1):
                key = code[:length]
                if key in SUPPLEMENTAL:
                    lookup[code] = {
                        'r': SUPPLEMENTAL[key],
                        'raw': f"{SUPPLEMENTAL[key]}% (supplemental)",
                        'c': False
                    }
                    filled += 1
                    break

    if filled:
        log(f"Filled {filled} gaps from supplemental table")

    return lookup


def load_existing_rates():
    """Load the current base_rates.b64 to get the set of codes we need."""
    if not RATES_FILE.exists():
        log("No existing base_rates.b64 found — starting fresh")
        return {}
    try:
        raw = RATES_FILE.read_text().strip()
        data = json.loads(gzip.decompress(base64.b64decode(raw)).decode())
        log(f"Loaded {len(data)} existing rate entries")
        return data
    except Exception as e:
        log(f"Could not load existing rates: {e}")
        return {}


def save_rates(lookup):
    """Compress and save lookup to data/base_rates.b64."""
    j = json.dumps(lookup, separators=(',', ':'))
    compressed = gzip.compress(j.encode())
    b64 = base64.b64encode(compressed).decode()
    RATES_FILE.write_text(b64)
    log(f"Saved base_rates.b64 ({len(b64)/1024:.1f} KB)")
    return b64


def inject_into_html(rates_b64):
    """Replace the BASERATES_B64 constant in index.html with fresh data."""
    if not HTML_FILE.exists():
        log(f"ERROR: {HTML_FILE} not found")
        sys.exit(1)

    html = HTML_FILE.read_text(encoding='utf-8')

    pattern = r'(const BASERATES_B64\s*=\s*")[^"]+(")'
    new_html, count = re.subn(pattern,
                               lambda m: m.group(1) + rates_b64 + m.group(2),
                               html)
    if count == 0:
        log("ERROR: Could not find BASERATES_B64 constant in index.html")
        sys.exit(1)

    # Also update the config rate display in the rate tiles if env vars are set
    sec122 = os.environ.get('SEC122_RATE')
    sec301 = os.environ.get('SEC301_RATE')
    if sec122:
        new_html = re.sub(
            r"(s122:)\s*\d+(\.*\d*)",
            lambda m: f"{m.group(1)}{float(sec122):.1f}".rstrip('0').rstrip('.'),
            new_html, count=1
        )
        log(f"Updated SEC122 rate to {sec122}%")
    if sec301:
        new_html = re.sub(
            r"(s301:)\s*\d+(\.*\d*)",
            lambda m: f"{m.group(1)}{float(sec301):.1f}".rstrip('0').rstrip('.'),
            new_html, count=1
        )
        log(f"Updated SEC301 rate to {sec301}%")

    HTML_FILE.write_text(new_html, encoding='utf-8')
    log(f"Injected fresh rates into index.html")


def main():
    log("Starting rate update...")
    log(f"Repo root: {REPO_ROOT}")

    # 1. Try to download fresh USITC data
    hts_data = download_hts_json()
    if not hts_data:
        log("WARNING: Could not download USITC data. Will use supplemental table only.")

    # 2. Build rate lookup (USITC data + supplemental fallback)
    lookup = build_rate_lookup(hts_data)
    log(f"Final lookup: {len(lookup)} entries")

    # 3. Save compressed data
    rates_b64 = save_rates(lookup)

    # 4. Inject into index.html
    inject_into_html(rates_b64)

    # 5. Print summary
    rate_dist = {}
    for v in lookup.values():
        r = v['r']
        rate_dist[r] = rate_dist.get(r, 0) + 1
    log(f"Rate distribution: { {f'{k}%': v for k,v in sorted(rate_dist.items())} }")
    log("Done ✓")


if __name__ == '__main__':
    main()
