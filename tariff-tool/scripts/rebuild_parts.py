#!/usr/bin/env python3
"""
rebuild_parts.py
----------------
Rebuilds data/parts_data.b64 and data/mat_lookup.b64 from a new parts
reference Excel file, then injects both into index.html.

Usage:
    python scripts/rebuild_parts.py path/to/parts_list.xlsx [path/to/material_types.xlsx]

The parts Excel should have columns:
    Part Number | Description | Basic Material | Plant | HTS Classification

The optional material_types Excel maps internal material codes to Steel/Aluminum/Copper/Other:
    Basic Material | Type
"""

import sys, re, json, gzip, base64
import pandas as pd
from pathlib import Path

REPO_ROOT   = Path(__file__).parent.parent
HTML_FILE   = REPO_ROOT / "index.html"
DATA_DIR    = REPO_ROOT / "data"
PARTS_FILE  = DATA_DIR / "parts_data.b64"
MAT_FILE    = DATA_DIR / "mat_lookup.b64"

PRIORITY_PLANTS = {'4200', '4700'}


def log(msg):
    print(f"[rebuild_parts] {msg}", flush=True)


def fmt_hts(code):
    if pd.isna(code):
        return ''
    d = re.sub(r'\D', '', str(code).strip())
    if len(d) == 8:
        return f'{d[:4]}.{d[4:6]}.{d[6:8]}'
    elif len(d) >= 10:
        d = d[:10]
        return f'{d[:4]}.{d[4:6]}.{d[6:8]}.{d[8:10]}'
    elif len(d) >= 6:
        return f'{d[:4]}.{d[4:6]}.{d[6:]}'
    return d


def load_mat_types(xlsx_path):
    if not xlsx_path or not Path(xlsx_path).exists():
        return {}
    df = pd.read_excel(xlsx_path, dtype=str)
    type_map = {}
    for _, row in df.iterrows():
        code = str(row.get('Basic Material', '')).strip()
        typ  = str(row.get('Type', '')).strip()
        if typ in ('Iron',): typ = 'Steel'
        cat  = {'Steel': 'S', 'Aluminum': 'A', 'Copper': 'C', 'Other': 'O'}.get(typ, '')
        if code and cat:
            type_map[code] = cat
    log(f"Loaded {len(type_map)} material type overrides")
    return type_map


def categorize(m, type_map):
    if pd.isna(m):
        return ''
    raw = str(m).strip()
    s = raw.upper()
    if raw in type_map:
        return type_map[raw]
    skip = {'', 'NAN', 'NOT APPLICABLE', '(NOT APPLICABLE)', 'N/A', 'SEE DRAWING',
            'VARIOUS', 'VERSCHIEDENE', '-', 'ROH', 'OHNE WERKSTOFF', 'NOT APPL'}
    if s in skip:
        return ''
    if re.match(r'^CM-\d', s) or re.match(r'^MAT\d', s) or re.match(r'^[-\d]', s):
        return ''
    non_metal = ['RUBBER', 'GUMMI', 'NBR', 'EPDM', 'FKM', 'VITON', 'PTFE', 'TEFLON',
                 'NEOPRENE', 'PLASTIC', 'KUNSTSTOFF', 'GRAPHIT', 'GRAFIT', 'GRAPHITE',
                 'KOHLE', 'ELASTOMER', 'SILICON', 'SILIKON', 'CERAMIC', 'GLASS',
                 'PAPER', 'WOOD', 'TURCITE', 'TURCON', 'NOMEX', 'INCONEL', 'NIMONIC',
                 'HASTELLOY', 'STELLIT', 'TITANIUM', 'TIALF']
    for kw in non_metal:
        if kw in s:
            return 'O'
    if not ('CRNI' in s or re.match(r'X\dCR', s)):
        for kw in ['CU-DHP', 'CU-ETP', 'CUZN', 'CUSN', 'SF-CU', 'MESSING',
                   'BRONZE', 'BRASS', 'DEVA-METALL', 'DEVA.METAL']:
            if kw in s:
                return 'C'
        if re.search(r'\bCU\b', s):
            return 'C'
    if re.search(r'\bAL\b', s) or re.match(r'AL(MG|SI|ZN)', s) or \
       s.startswith('EN AW') or s.startswith('EN AC'):
        return 'A'
    steel_kw = ['STEEL', 'STAHL', 'STAINLESS', 'ACIER', 'CARBON STEEL', 'CAST IRON',
                'GUSSEISEN', 'EN-GJL', 'EN-GJS', 'S235', 'S355', 'P235', 'P265',
                'AISI', 'ASTM A', 'SA193', 'SA194', 'X2CR', 'X5CR', 'X6CR', 'X20CR',
                'X22CR', '42CRMO', '21CRMOV', 'HSS', 'IRON', 'EISEN']
    for kw in steel_kw:
        if kw in s:
            return 'S'
    if re.search(r'\b(STEEL|STAHL|IRON)\b', s):
        return 'S'
    return ''


def build_parts(df, type_map):
    df['cat'] = df['Basic Material'].apply(lambda m: categorize(m, type_map))
    df['mat_raw'] = df['Basic Material'].apply(
        lambda x: '' if pd.isna(x) or str(x).strip() in ('nan', 'not applicable',
                  '(Not Applicable)', '') else str(x).strip()
    )
    df['is_priority'] = df['Plant'].isin(PRIORITY_PLANTS)
    df['hts_fmt'] = df['HTS Classification'].apply(fmt_hts)

    def priority(row):
        base = 4 if row['is_priority'] else 1
        if row['cat'] in ('S', 'A', 'C', 'O'):
            return base + 2
        if row['mat_raw']:
            return base + 1
        return base

    df['priority'] = df.apply(priority, axis=1)

    # Parts DB (for HTS + fuzzy lookup)
    parts_records = [
        {'pn': str(r['Part Number']).strip(),
         'desc': str(r['Description']).strip(),
         'hts': r['hts_fmt'],
         'p': 1 if r['is_priority'] else 0}
        for _, r in df.iterrows()
        if str(r['Part Number']).strip()
    ]

    # Mat DB (best entry per part number)
    df_best = df.sort_values('priority', ascending=False)\
                .drop_duplicates(subset='Part Number', keep='first')
    mat_lookup = {}
    for _, row in df_best.iterrows():
        pn = str(row['Part Number']).strip()
        if pn:
            mat_lookup[pn] = [row['mat_raw'], row['cat']]

    log(f"Parts DB: {len(parts_records)} records")
    log(f"Mat lookup: {len(mat_lookup)} entries")
    return parts_records, mat_lookup


def compress_and_save(data, path):
    j = json.dumps(data, separators=(',', ':'))
    b64 = base64.b64encode(gzip.compress(j.encode())).decode()
    Path(path).write_text(b64)
    log(f"Saved {Path(path).name} ({len(b64)/1024:.1f} KB)")
    return b64


def inject(const_name, b64, html):
    pattern = f'(const {const_name}\\s*=\\s*")[^"]+(")'
    new_html, count = re.subn(pattern, lambda m: m.group(1) + b64 + m.group(2), html)
    if count == 0:
        log(f"ERROR: Could not find {const_name} in index.html")
        sys.exit(1)
    return new_html


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/rebuild_parts.py parts.xlsx [material_types.xlsx]")
        sys.exit(1)

    parts_path = Path(sys.argv[1])
    mat_types_path = sys.argv[2] if len(sys.argv) > 2 else None

    if not parts_path.exists():
        log(f"ERROR: {parts_path} not found")
        sys.exit(1)

    log(f"Loading parts from {parts_path}")
    df = pd.read_excel(parts_path, dtype=str)
    log(f"Loaded {len(df)} rows")

    type_map = load_mat_types(mat_types_path)
    parts_records, mat_lookup = build_parts(df, type_map)

    parts_b64 = compress_and_save(parts_records, PARTS_FILE)
    mat_b64   = compress_and_save(mat_lookup, MAT_FILE)

    html = HTML_FILE.read_text(encoding='utf-8')
    html = inject('PARTS_B64', parts_b64, html)
    html = inject('MATDB_B64', mat_b64, html)
    HTML_FILE.write_text(html, encoding='utf-8')
    log("Injected into index.html ✓")
    log("Done. Commit with: git add data/ index.html && git commit -m 'Update parts database'")


if __name__ == '__main__':
    main()
