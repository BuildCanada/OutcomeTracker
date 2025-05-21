#!/usr/bin/env python3
import sys, csv, json, requests, io, re
from urllib.parse import urlparse, parse_qs

if len(sys.argv) < 2:
    sys.exit("Usage: python csv_to_json.py <data_csv_url> [output.json]")

data_url = sys.argv[1]
out_path = sys.argv[2] if len(sys.argv) > 2 else None

# extract pid
qs = parse_qs(urlparse(data_url).query)
pid = qs.get('pid', [None])[0]
if not pid:
    sys.exit("Error: 'pid' parameter not found in URL")

# metadata URL
base_pid = pid[:-2]
meta_url = (
    "https://www150.statcan.gc.ca/t1/tbl1/en/dtl!downloadDbLoadingData-nonTraduit.action"
    f"?pid={base_pid}&file={pid}-symbolsSeparate.csv"
)

def fetch_data(url):
    r = requests.get(url); r.raise_for_status()
    buf = io.StringIO(r.text)
    hdr = next(csv.reader(buf))
    clean = [h.strip().lstrip('\ufeff').strip().strip('"') for h in hdr]
    dr = csv.DictReader(io.StringIO(r.text), fieldnames=clean)
    next(dr)
    out={}
    for row in dr:
        g, d = row['GEO'], row['REF_DATE']
        v = float(row['VALUE']) if row['VALUE'] else None
        out.setdefault(g, []).append([d, v])
    return out

def fetch_meta(url):
    r = requests.get(url)
    # filter out any error lines
    lines = [ln for ln in r.text.splitlines()
             if "Failed to get the database loading data" not in ln and ln.strip()]
    meta = {}
    for i, raw in enumerate(lines[:5]):
        v = raw.strip().lstrip('\ufeff').strip().strip('"')
        if i==0:
            meta['name']=v
        else:
            if ':' in v:
                k,val = v.split(':',1)
                meta[k.strip()]=val.strip()
    return meta

output = {
    "data": fetch_data(data_url),
    # "metadata": fetch_meta(meta_url)
}
# pretty-print
pretty = json.dumps(output, indent=2, sort_keys=True)

# collapse any two-element arrays onto one line:
#   [\n    "date",\n    value\n  ]  → [ "date", value ]
pattern = re.compile(r'\[\s*\n\s*"([^"]+)",\s*([0-9]+(?:\.[0-9]+)?)\s*\n\s*\]', re.MULTILINE)
collapsed = pattern.sub(r'[ "\1", \2 ]', pretty)

if out_path:
    with open(out_path, 'w') as f:
        f.write(collapsed)
else:
    print(collapsed)
