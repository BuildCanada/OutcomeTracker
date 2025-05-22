#!/usr/bin/env python3
import sys, csv, json, requests, io, re, logging
from urllib.parse import urlparse, parse_qs

# set up logging to stderr
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s %(message)s',
    stream=sys.stderr
)
log = logging.getLogger(__name__)

if len(sys.argv) < 2:
    log.error("Usage: python csv_to_json.py <data_csv_url> [output.json] [facet]")
    sys.exit(1)

data_url = sys.argv[1]
out_path = sys.argv[2] if len(sys.argv) > 2 else None
FACET = sys.argv[3] if len(sys.argv) > 3 else "GEO"

log.debug(f"Data URL: {data_url!r}")
log.debug(f"Output path: {out_path!r}")
log.debug(f"Facet column: {FACET!r}")

# extract pid
qs = parse_qs(urlparse(data_url).query)
pid = qs.get('pid', [None])[0]
if not pid:
    log.error("Error: 'pid' parameter not found in URL")
    sys.exit(1)
log.debug(f"Extracted pid: {pid}")

# metadata URL (unused for now)
base_pid = pid[:-2]
meta_url = (
    "https://www150.statcan.gc.ca/t1/tbl1/en/dtl!downloadDbLoadingData-nonTraduit.action"
    f"?pid={base_pid}&file={pid}-symbolsSeparate.csv"
)
log.debug(f"Metadata URL: {meta_url}")

def fetch_data(url):
    log.info(f"Fetching data CSV from {url}")
    r = requests.get(url); r.raise_for_status()
    text = r.text
    log.debug(f"Downloaded {len(text)} bytes")
    buf = io.StringIO(text)

    hdr = next(csv.reader(buf))
    clean = [h.strip().lstrip('\ufeff').strip().strip('"') for h in hdr]
    log.debug(f"Cleaned headers: {clean}")

    dr = csv.DictReader(io.StringIO(text), fieldnames=clean)
    next(dr)  # skip header
    out = {}
    row_count = 0
    for row in dr:
        row_count += 1
        key = row.get(FACET)
        if key is None:
            log.warning(f"Row {row_count} missing facet '{FACET}': {row}")
            continue
        date = row['REF_DATE']
        val = float(row['VALUE']) if row['VALUE'] else None
        out.setdefault(key, []).append([date, val])
    log.info(f"Parsed {row_count} rows into {len(out)} series")
    return out

# def fetch_meta(url):
#     … (you can add similar logging if re-adding metadata)

output = {
    "data": fetch_data(data_url),
    # "metadata": fetch_meta(meta_url)
}

log.info(f"Serializing JSON")
pretty = json.dumps(output, indent=2, sort_keys=True)

# collapse two-element arrays onto one line
pattern = re.compile(
    r'\[\s*\n\s*"([^"]+)",\s*(null|-?[0-9]+(?:\.[0-9]+)?)\s*\n\s*\]',
    re.MULTILINE
)
collapsed = pattern.sub(r'[ "\1", \2 ]', pretty)
log.debug("Applied array-collapse regex")

if out_path:
    log.info(f"Writing output to {out_path}")
    with open(out_path, 'w') as f:
        f.write(collapsed)
else:
    log.info("Writing output to stdout")
    print(collapsed)
