"""
process_metafields_v2.py
========================
Task A: Fill missing Watch Brand / Watch Size / Watch Movement metafields.
Task B: Add Watch Gender and Watch Type metafields.

Input : watch_products_export_070426.csv
Output: watches-final-metafields.csv
"""

import csv
import re

INPUT_FILE  = '/home/user/shopify-watches-full-export/watch_products_export_070426.csv'
OUTPUT_FILE = '/home/user/shopify-watches-full-export/watches-final-metafields.csv'

# ── Column names ──────────────────────────────────────────────────────────────
COL_BRAND    = 'Watch Brand (product.metafields.custom.watch_brand)'
COL_SIZE     = 'Watch Size (product.metafields.custom.watch_size)'
COL_MOVEMENT = 'Watch Movement (product.metafields.custom.watch_movement)'
COL_GENDER   = 'Watch Gender (product.metafields.custom.watch_gender)'
COL_TYPE     = 'Watch Type (product.metafields.custom.watch_type)'

# ── Valid sizes (choice list) ─────────────────────────────────────────────────
VALID_SIZES = {f'{i}mm' for i in range(15, 46)}

# Sizes that classify as ladies (strictly under 33mm)
LADIES_SIZES = {f'{i}mm' for i in range(15, 33)}

# ── Multi-word brands (pattern → canonical name) ──────────────────────────────
MULTI_WORD_BRANDS = [
    ('Hegde & Goyle',        'Hegde & Goyle'),
    ('Henri Sandoz & Fils',  'Henri Sandoz & Fils'),
    ('Henri Sandoz',         'Henri Sandoz'),
    ('West End Watch',       'West End'),
    ('West End',             'West End'),
    ('Favre-Leuba',          'Favre Leuba'),
    ('Favre Leuba',          'Favre Leuba'),
    ('Anglo Swiss Watch',    'Anglo Swiss'),
    ('Anglo Swiss',          'Anglo Swiss'),
    ('Hegde Golay',          'Hegde Golay'),
    ('Tag Heuer',            'Tag Heuer'),
    ('Universal Genève',     'Universal Genève'),
    ('Universal Geneve',     'Universal Geneve'),
    ('Must de Cartier',      'Cartier'),
    ('Lassale by Seiko',     'Lassale'),
    ('Rodolphe By Longines', 'Rodolphe'),
    ('Caravelle by Bulova',  'Caravelle'),
    ('Shreeshyla by Hegde',  'Hegde'),
    ('King Seiko',           'Seiko'),
]

# ── Movement normalisation ────────────────────────────────────────────────────
MOVEMENT_MAP = {
    'automatic':      'Automatic',
    'self-winding':   'Automatic',
    'self winding':   'Automatic',
    'manual':         'Manual',
    'hand-wound':     'Manual',
    'hand wound':     'Manual',
    'manual winding': 'Manual',
    'manual wind':    'Manual',
    'quartz':         'Quartz',
    'digital':        'Digital',
    'mecaquartz':     'Mecaquartz',
    'tuning fork':    'Tuning Fork',
}

def normalise_movement(raw):
    return MOVEMENT_MAP.get(raw.strip().lower(), raw.strip().title())

# ── Watch type keyword map (order = priority; multiple matches joined with " / ") ──
TYPE_RULES = [
    (re.compile(r'\bjump.?hour\b', re.I),           'Jump Hour'),
    (re.compile(r'\bchronograph\b', re.I),           'Chronograph'),
    (re.compile(r'\bchrono\b', re.I),                'Chronograph'),
    (re.compile(r'\bmoon.?phase\b', re.I),           'Moonphase'),
    (re.compile(r'\bdiver\b', re.I),                 'Diver'),
    (re.compile(r'\bdive watch\b', re.I),            'Diver'),
    (re.compile(r'\bpresidential\b', re.I),          'Presidential'),
    (re.compile(r'\bskeleton\b', re.I),              'Skeleton'),
    (re.compile(r'\bperpetual.?calendar\b', re.I),   'Perpetual Calendar'),
    (re.compile(r'\btriple.?calen[de]r\b', re.I),    'Triple Calendar'),
    (re.compile(r'\bworld.?time\b', re.I),           'World Time'),
    (re.compile(r'\bpower.?reserve\b', re.I),        'Power Reserve'),
    (re.compile(r'\balarm\b', re.I),                 'Alarm'),
    (re.compile(r'\bgmt\b', re.I),                   'GMT'),
    (re.compile(r'\bpilot\b', re.I),                 'Pilot'),
    (re.compile(r'\baviator\b', re.I),               'Pilot'),
    (re.compile(r'\bfield watch\b', re.I),           'Field'),
    (re.compile(r'\btonneau\b', re.I),               'Tonneau'),
    (re.compile(r'\btank\b', re.I),                  'Tank'),
    (re.compile(r'\bdress\b', re.I),                 'Dress'),
    (re.compile(r'\bdigital\b', re.I),               'Digital'),
    (re.compile(r'\bregulator\b', re.I),             'Regulator'),
]

# ── Regex helpers ─────────────────────────────────────────────────────────────
SIZE_MOV_PAREN_RE    = re.compile(
    r'\((\d+(?:\.\d+)?mm(?:\s*[xX×]\s*\d+(?:\.\d+)?mm)?)\s*[;,]\s*([^)]+?)\s*\)',
    re.I)
SIZE_MOV_BRACKET_RE  = re.compile(
    r'\[(\d+(?:\.\d+)?mm(?:\s*[xX×]\s*\d+(?:\.\d+)?mm)?)\]\s*'
    r'(Automatic|Self-Winding|Manual\s*Winding|Manual\s*Wind|Manual|'
    r'Quartz|Digital|Mecaquartz)',
    re.I)
SIZE_BRACKET_ONLY_RE = re.compile(r'\[(\d+(?:\.\d+)?mm)\]', re.I)
MOV_PAREN_RE         = re.compile(
    r'\((Automatic|Self-Winding|Manual\s*Winding|Manual\s*Wind|Manual|'
    r'Quartz|Digital|Mecaquartz|Tuning\s*Fork)\)',
    re.I)
MOV_SCAN_RE          = re.compile(
    r'\b(automatic|self-winding|self\s+winding|manual\s+winding|manual\s+wind|'
    r'hand-wound|hand\s+wound|manual|quartz|digital|mecaquartz|tuning\s+fork)\b',
    re.I)
PIPE_SIZE_RE         = re.compile(r'\|\s*(\d+mm)\s*(?:\||$)', re.I)
PIPE_MOV_RE          = re.compile(
    r'\|\s*(Automatic|Self-Winding|Manual\s*Winding|Manual\s*Wind|Manual|'
    r'Quartz|Digital|Mecaquartz)\s*(?:\||$)',
    re.I)


def _clean_size(raw):
    m = re.fullmatch(r'(\d+)mm', raw.strip(), re.I)
    if m and int(m.group(1)) in range(15, 46):
        return f'{m.group(1)}mm'
    return ''


def extract_brand(brand_model_str):
    s = brand_model_str.strip()
    for pattern, canonical in MULTI_WORD_BRANDS:
        if re.match(re.escape(pattern), s, re.I):
            return canonical
    words = s.split()
    return words[0] if words else ''


def _brand_from_prefix(prefix):
    s = prefix.strip()
    if not s or s[0].isdigit():
        return ''
    return extract_brand(s)


def _try_bracket_and_pipe(text):
    """Return (size, movement) from bracket/pipe patterns."""
    size = movement = ''

    bm = SIZE_MOV_BRACKET_RE.search(text)
    if bm:
        return _clean_size(bm.group(1)), normalise_movement(bm.group(2))

    sb = SIZE_BRACKET_ONLY_RE.search(text)
    if sb:
        size = _clean_size(sb.group(1))

    ps = PIPE_SIZE_RE.search(text)
    if ps and not size:
        size = _clean_size(ps.group(1))

    pm = PIPE_MOV_RE.search(text)
    if pm:
        return size, normalise_movement(pm.group(1))

    mp = MOV_PAREN_RE.search(text)
    if mp:
        return size, normalise_movement(mp.group(1))

    mv = MOV_SCAN_RE.search(text)
    if mv:
        movement = normalise_movement(mv.group(1))

    return size, movement


def parse_title(title):
    """Return (brand, size, movement) from a product title."""
    brand = size = movement = ''
    if not title:
        return brand, size, movement

    # Strip optional year prefix
    working = title
    ym = re.match(r"^\d{4}s?\s+(.+)", title)
    if ym:
        working = ym.group(1)

    # Pattern 1/4: has (Ref. X) or (Ref: X) or bare "Ref. X"
    ref_m = re.match(r'^(.+?)\s+\(Ref[\.:][^)]*\)', working, re.I)
    if not ref_m:
        ref_m = re.match(r'^(.+?)\s+Ref\.\s*\S+', working, re.I)
    if ref_m:
        brand = _brand_from_prefix(ref_m.group(1))
        sm = SIZE_MOV_PAREN_RE.search(working)
        if sm:
            size     = _clean_size(sm.group(1))
            movement = normalise_movement(sm.group(2))
        else:
            size, movement = _try_bracket_and_pipe(working)
        return brand, size, movement

    # Pattern 2: (Ymm; Movement) or (Ymm, Movement) without Ref
    sm = SIZE_MOV_PAREN_RE.search(working)
    if sm:
        prefix = working[:sm.start()].strip().rstrip('-– ')
        brand    = _brand_from_prefix(prefix)
        size     = _clean_size(sm.group(1))
        movement = normalise_movement(sm.group(2))
        return brand, size, movement

    # Pattern 3: bracket / pipe
    s2, m2 = _try_bracket_and_pipe(working)
    if s2 or m2:
        pfx_m = re.match(r'^(.+?)(?:\s+[-–]\s|\s*\||\s*\[)', working)
        prefix = pfx_m.group(1).strip() if pfx_m else working.split('|')[0].strip()
        brand = _brand_from_prefix(prefix)
        return brand, s2, m2

    # Pattern 4: pipe-separated size only
    ps = PIPE_SIZE_RE.search(working)
    if ps:
        brand = _brand_from_prefix(working.split('|')[0].strip().rstrip('-– '))
        size  = _clean_size(ps.group(1))
        pm = PIPE_MOV_RE.search(working)
        if pm:
            movement = normalise_movement(pm.group(1))
        return brand, size, movement

    # Pattern 5: movement keyword in parens only
    mp = MOV_PAREN_RE.search(working)
    if mp:
        prefix   = working[:mp.start()].strip().rstrip('-– ')
        brand    = _brand_from_prefix(prefix)
        movement = normalise_movement(mp.group(1))
        return brand, size, movement

    # Final fallback: extract brand from title start
    pfx = re.split(r'\s+[-–]\s|\s*\||\s*\(|\s*\[', working)[0].strip()
    brand = _brand_from_prefix(pfx)
    return brand, size, movement


def get_watch_type(title):
    """Return watch type(s) detected in title, or empty string."""
    seen = []
    seen_canonical = set()
    for pattern, canonical in TYPE_RULES:
        if pattern.search(title) and canonical not in seen_canonical:
            seen.append(canonical)
            seen_canonical.add(canonical)
    return ' / '.join(seen)


def get_watch_gender(title, size):
    """Return 'Ladies' if applicable, else empty string."""
    title_lower = title.lower()
    if 'ladies' in title_lower or 'lady' in title_lower or "women's" in title_lower or 'womens' in title_lower:
        return 'Ladies'
    if size and size in LADIES_SIZES:
        return 'Ladies'
    return ''


# ── Main processing ───────────────────────────────────────────────────────────
with open(INPUT_FILE, encoding='utf-8', newline='') as infile:
    reader      = csv.DictReader(infile)
    orig_headers = reader.fieldnames[:]
    rows         = list(reader)

# Build output headers: insert Gender + Type after Watch Size column
new_headers = list(orig_headers)
if COL_GENDER not in new_headers:
    insert_at = new_headers.index(COL_SIZE) + 1
    new_headers.insert(insert_at, COL_GENDER)
    new_headers.insert(insert_at + 1, COL_TYPE)

# Process rows
for row in rows:
    title = row.get('Title', '').strip()

    if title:
        existing_brand = row.get(COL_BRAND, '').strip()
        existing_size  = row.get(COL_SIZE,  '').strip()
        existing_mov   = row.get(COL_MOVEMENT, '').strip()

        # Task A: fill missing fields
        if not (existing_brand and existing_size and existing_mov):
            parsed_brand, parsed_size, parsed_mov = parse_title(title)
            if not existing_brand:
                row[COL_BRAND]    = parsed_brand
            if not existing_size:
                row[COL_SIZE]     = parsed_size
            if not existing_mov:
                row[COL_MOVEMENT] = parsed_mov

        # Re-read (may have just been filled)
        final_size = row.get(COL_SIZE, '').strip()

        # Task B: gender + type (always populate)
        row[COL_GENDER] = get_watch_gender(title, final_size)
        row[COL_TYPE]   = get_watch_type(title)

    else:
        # Continuation row: clear all metafields
        row[COL_BRAND]    = ''
        row[COL_SIZE]     = ''
        row[COL_MOVEMENT] = ''
        row[COL_GENDER]   = ''
        row[COL_TYPE]     = ''

with open(OUTPUT_FILE, 'w', encoding='utf-8', newline='') as outfile:
    writer = csv.DictWriter(outfile, fieldnames=new_headers, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(rows)

print(f'Done → {OUTPUT_FILE}')

# ── QA summary ────────────────────────────────────────────────────────────────
product_rows = [r for r in rows if r.get('Title', '').strip()]
total = len(product_rows)
print(f'\nProducts: {total}')
print(f'Brand:    {sum(1 for r in product_rows if r.get(COL_BRAND)):4d} ({sum(1 for r in product_rows if r.get(COL_BRAND))*100//total}%)')
print(f'Size:     {sum(1 for r in product_rows if r.get(COL_SIZE)):4d} ({sum(1 for r in product_rows if r.get(COL_SIZE))*100//total}%)')
print(f'Movement: {sum(1 for r in product_rows if r.get(COL_MOVEMENT)):4d} ({sum(1 for r in product_rows if r.get(COL_MOVEMENT))*100//total}%)')
print(f'Gender:   {sum(1 for r in product_rows if r.get(COL_GENDER)):4d}')
print(f'Type:     {sum(1 for r in product_rows if r.get(COL_TYPE)):4d}')

# Gender breakdown
from collections import Counter
genders = Counter(r.get(COL_GENDER,'') for r in product_rows)
types   = Counter(r.get(COL_TYPE,'') for r in product_rows if r.get(COL_TYPE,''))
print(f'\nGender breakdown: {dict(genders)}')
print(f'\nTop types:')
for t, c in types.most_common(20):
    print(f'  {c:4d}  {t}')
