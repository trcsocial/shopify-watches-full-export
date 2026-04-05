import csv
import re
import sys

INPUT_FILE = '/home/user/shopify-watches-full-export/watches-full-products-export.csv'
OUTPUT_FILE = '/home/user/shopify-watches-full-export/watches-updated-metafields.csv'

# Column headers for the three target metafields
COL_WATCH_SIZE = 'watch-size (product.metafields.custom.watch_size)'
COL_WATCH_BRAND = 'Watch Brand (product.metafields.custom.watch_brand)'
COL_WATCH_MOVEMENT = 'Watch Movement (product.metafields.custom.watch_movement)'

# Valid sizes for the choice list (15mm–45mm, whole mm only)
VALID_SIZES = {f'{i}mm' for i in range(15, 46)}

# Known multi-word brands — order matters: longer/more-specific first
# Hyphen variants are listed alongside their canonical form
MULTI_WORD_BRANDS = [
    ('Hegde & Goyle',      'Hegde & Goyle'),
    ('Henri Sandoz & Fils','Henri Sandoz & Fils'),
    ('Henri Sandoz',       'Henri Sandoz'),
    ('West End Watch',     'West End'),
    ('West End',           'West End'),
    ('Favre-Leuba',        'Favre Leuba'),   # hyphenated variant
    ('Favre Leuba',        'Favre Leuba'),
    ('Anglo Swiss Watch',  'Anglo Swiss'),
    ('Anglo Swiss',        'Anglo Swiss'),
    ('Hegde Golay',        'Hegde Golay'),
    ('Tag Heuer',          'Tag Heuer'),
    ('Universal Genève',   'Universal Genève'),
    ('Universal Geneve',   'Universal Geneve'),
    ('Must de Cartier',    'Cartier'),
    ('Lassale by Seiko',   'Lassale'),
    ('Rodolphe By Longines', 'Rodolphe'),
    ('Caravelle by Bulova', 'Caravelle'),
    ('Shreeshyla by Hegde', 'Hegde'),
]


def extract_brand(brand_model_str):
    """Extract brand name from 'Brand Model...' string."""
    s = brand_model_str.strip()
    for pattern, canonical in MULTI_WORD_BRANDS:
        if re.match(re.escape(pattern), s, re.IGNORECASE):
            return canonical
    # Fall back to first word
    words = s.split()
    return words[0] if words else ''


MOVEMENT_KEYWORDS = {
    'automatic': 'Automatic',
    'self-winding': 'Automatic',
    'self winding': 'Automatic',
    'manual': 'Manual',
    'hand-wound': 'Manual',
    'hand wound': 'Manual',
    'manual winding': 'Manual',
    'manual wind': 'Manual',
    'quartz': 'Quartz',
    'digital': 'Digital',
    'mecaquartz': 'Mecaquartz',
    'tuning fork': 'Tuning Fork',
}

def normalise_movement(raw):
    """Map raw movement text to a canonical value."""
    low = raw.strip().lower()
    return MOVEMENT_KEYWORDS.get(low, raw.strip().title())


SIZE_MOV_PAREN_RE = re.compile(
    r'\((\d+(?:\.\d+)?mm(?:\s*[xX]\s*\d+(?:\.\d+)?mm)?)\s*[;,]\s*([^)]+?)\s*\)',
    re.IGNORECASE
)
SIZE_MOV_BRACKET_RE = re.compile(
    r'\[(\d+(?:\.\d+)?mm(?:\s*[xX]\s*\d+(?:\.\d+)?mm)?)\]\s*(Automatic|Manual|Quartz|Digital|Mecaquartz)',
    re.IGNORECASE
)
SIZE_BRACKET_ONLY_RE = re.compile(
    r'\[(\d+(?:\.\d+)?mm)\]',
    re.IGNORECASE
)


def _clean_size(raw):
    """Return size string if valid choice-list value, else empty string."""
    s = raw.strip().lower()
    # Must be a whole-number single dimension in 15–45mm
    m = re.fullmatch(r'(\d+)mm', s)
    if m and int(m.group(1)) in range(15, 46):
        return f'{m.group(1)}mm'
    return ''


def _brand_from_prefix(prefix):
    """Extract brand from the leading 'Brand Model' part of a title.
    Only returns a value if the first token looks like a proper brand name
    (starts with uppercase letter, not a year or number).
    """
    s = prefix.strip()
    # Skip if starts with a digit (year-prefixed titles like "1978 Rolex...")
    if not s or s[0].isdigit():
        return ''
    return extract_brand(s)


# Movement keyword pattern for scanning title text
_MOV_SCAN_RE = re.compile(
    r'\b(automatic|self-winding|self\s+winding|manual\s+winding|manual\s+wind|'
    r'hand-wound|hand\s+wound|manual|quartz|digital|mecaquartz|tuning\s+fork)\b',
    re.IGNORECASE
)
# Pipe-separated size: | 38mm |
_PIPE_SIZE_RE = re.compile(r'\|\s*(\d+mm)\s*(?:\||$)', re.IGNORECASE)
# Pipe-separated movement keyword
_PIPE_MOV_RE  = re.compile(
    r'\|\s*(Automatic|Self-Winding|Manual\s*Winding|Manual\s*Wind|Manual|'
    r'Quartz|Digital|Mecaquartz)\s*(?:\||$)', re.IGNORECASE
)
# Size before Ref: e.g. "Edox Automatic (39mm) – Ref. 200217"
_SIZE_BEFORE_REF_RE = re.compile(r'\((\d+mm)\)\s*[-–]\s*Ref\.', re.IGNORECASE)
# Simple paren movement: (Automatic) / (Manual) etc.
_MOV_PAREN_RE = re.compile(
    r'\((Automatic|Self-Winding|Manual\s*Winding|Manual\s*Wind|Manual|'
    r'Quartz|Digital|Mecaquartz|Tuning\s*Fork)\)',
    re.IGNORECASE
)


def _try_bracket_and_pipe(working, prefix_override=None):
    """Try bracket and pipe patterns on 'working' string.
    Returns (size, movement) — either may be empty.
    """
    size = movement = ''

    # Bracket + movement keyword: [Ymm] Movement
    bm = SIZE_MOV_BRACKET_RE.search(working)
    if bm:
        size     = _clean_size(bm.group(1))
        movement = normalise_movement(bm.group(2))
        return size, movement

    # Bracket only (no movement keyword next)
    sb = SIZE_BRACKET_ONLY_RE.search(working)
    if sb:
        size = _clean_size(sb.group(1))

    # Pipe-separated size: | 38mm |
    ps = _PIPE_SIZE_RE.search(working)
    if ps and not size:
        size = _clean_size(ps.group(1))

    # Pipe-separated movement keyword
    pm = _PIPE_MOV_RE.search(working)
    if pm:
        movement = normalise_movement(pm.group(1))
        return size, movement

    # Simple paren movement: (Automatic) etc.
    mp = _MOV_PAREN_RE.search(working)
    if mp:
        movement = normalise_movement(mp.group(1))
        return size, movement

    # Movement keyword anywhere in text (last resort)
    mv = _MOV_SCAN_RE.search(working)
    if mv:
        movement = normalise_movement(mv.group(1))

    return size, movement


def parse_title(title):
    """
    Parse a product title and return (brand, size, movement).
    Returns empty strings for fields that cannot be reliably determined.

    Handles:
      1. Standard:  Brand Model (Ref. X) [text] (Ymm; Movement)
      2. No-Ref:    Brand Model (Ymm; Movement)  or  (Ymm, Movement)
      3. Brackets:  Brand Model [Ymm] Movement
      4. Ref-colon: Brand Model (Ref: X) (Ymm, Movement)
      5. Year-prefix: 1978 Brand Model (Ref: X) (Ymm, Movement)
      6. Pipe-separated: Brand – notes | 38mm | Automatic
      7. Size before Ref: Brand (39mm) – Ref. XXX
    """
    brand = size = movement = ''

    if not title:
        return brand, size, movement

    # ── Strip optional year prefix e.g. "1978 " or "1980s " ─────────────────
    working = title
    year_m  = re.match(r"^(\d{4}s?)\s+(.+)", title)
    if year_m:
        working = year_m.group(2)

    # ── Pattern 1 & 4: title contains (Ref. X) or (Ref: X) ──────────────────
    ref_match = re.match(r'^(.+?)\s+\(Ref[\.:][^)]*\)', working, re.IGNORECASE)
    if not ref_match:
        # Try inline "Ref." not wrapped in parens: "... Ref. 200217"
        ref_match = re.match(r'^(.+?)\s+Ref\.\s*\S+', working, re.IGNORECASE)
    if ref_match:
        brand = _brand_from_prefix(ref_match.group(1))
        rest  = working[ref_match.end():]

        sm = SIZE_MOV_PAREN_RE.search(working)
        if sm:
            size     = _clean_size(sm.group(1))
            movement = normalise_movement(sm.group(2))
        else:
            size, movement = _try_bracket_and_pipe(working)

        return brand, size, movement

    # ── Pattern 2: (Ymm; Movement) or (Ymm, Movement) with no Ref ────────────
    sm = SIZE_MOV_PAREN_RE.search(working)
    if sm:
        prefix = working[:sm.start()].strip().rstrip('-– ')
        brand    = _brand_from_prefix(prefix)
        size     = _clean_size(sm.group(1))
        movement = normalise_movement(sm.group(2))
        return brand, size, movement

    # ── Pattern 3 & 3b / pipes ───────────────────────────────────────────────
    s2, m2 = _try_bracket_and_pipe(working)
    if s2 or m2:
        # Find prefix: everything before the first standalone separator (spaced dash/pipe/bracket)
        # Use spaced dashes only, to avoid splitting hyphenated brand names
        pfx_m = re.match(r'^(.+?)(?:\s+[-–]\s|\s*\||\s*\[)', working)
        prefix = pfx_m.group(1).strip() if pfx_m else working.split('|')[0].strip()
        brand = _brand_from_prefix(prefix)
        return brand, s2, m2

    # ── Pattern 6: pipe-size only (no bracket) ───────────────────────────────
    ps = _PIPE_SIZE_RE.search(working)
    if ps:
        size  = _clean_size(ps.group(1))
        parts = working.split('|')
        brand = _brand_from_prefix(parts[0].strip().rstrip('-– '))
        pm = _PIPE_MOV_RE.search(working)
        if pm:
            movement = normalise_movement(pm.group(1))
        return brand, size, movement

    # ── Pattern 7: movement keyword in parens / text, no size info ───────────
    mp = _MOV_PAREN_RE.search(working)
    if mp:
        prefix = working[:mp.start()].strip().rstrip('-– ')
        brand    = _brand_from_prefix(prefix)
        movement = normalise_movement(mp.group(1))
        return brand, size, movement

    # ── Final fallback: extract brand from start of title ────────────────────
    # Split only on spaced separators (not internal hyphens) to preserve hyphenated brand names
    pfx = re.split(r'\s+[-–]\s|\s*\||\s*\(|\s*\[', working)[0].strip()
    brand = _brand_from_prefix(pfx)
    return brand, size, movement


# ── Main processing ──────────────────────────────────────────────────────────

with open(INPUT_FILE, encoding='utf-8', newline='') as infile:
    reader = csv.DictReader(infile)
    original_headers = reader.fieldnames[:]

    # Insert new columns right after the existing watch_size column
    new_headers = list(original_headers)
    if COL_WATCH_BRAND not in new_headers:
        insert_after = COL_WATCH_SIZE
        idx = new_headers.index(insert_after) + 1
        new_headers.insert(idx, COL_WATCH_BRAND)
        new_headers.insert(idx + 1, COL_WATCH_MOVEMENT)

    rows = list(reader)

# Carry values across product rows (continuation rows share same product)
current_brand = current_size = current_movement = ''

processed = []
for row in rows:
    title = row.get('Title', '').strip()

    if title:
        # New product — parse title
        current_brand, current_size, current_movement = parse_title(title)

        # Write metafields on this (first) row
        row[COL_WATCH_SIZE]     = current_size
        row[COL_WATCH_BRAND]    = current_brand
        row[COL_WATCH_MOVEMENT] = current_movement
    else:
        # Continuation row (variant / image) — clear metafields (Shopify only
        # needs them on the first product row)
        row[COL_WATCH_SIZE]     = ''
        row[COL_WATCH_BRAND]    = ''
        row[COL_WATCH_MOVEMENT] = ''

    processed.append(row)

# Write output
with open(OUTPUT_FILE, 'w', encoding='utf-8', newline='') as outfile:
    writer = csv.DictWriter(outfile, fieldnames=new_headers, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(processed)

print(f'Done. Written to {OUTPUT_FILE}')
print(f'Total rows: {len(processed)}')

# Quick QA — show sample of parsed values
print('\nSample extractions:')
seen = set()
for row in processed:
    t = row.get('Title', '').strip()
    if t and t not in seen:
        seen.add(t)
        b = row[COL_WATCH_BRAND]
        s = row[COL_WATCH_SIZE]
        m = row[COL_WATCH_MOVEMENT]
        if b or s or m:
            print(f'  Title: {t[:70]}')
            print(f'  Brand={b!r}  Size={s!r}  Movement={m!r}')
            print()
        if len(seen) >= 30:
            break
