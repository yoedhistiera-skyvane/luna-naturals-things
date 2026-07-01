#!/usr/bin/env python3
import csv, json, re, sys
from collections import defaultdict

SRC = "/Users/sproutoffice/Downloads/Luna-Naturals-LP-Report-20-30-Jun-2026.csv"

def f(x):
    x = (x or "").strip()
    if x == "":
        return 0.0
    try:
        return float(x)
    except:
        return 0.0

rows = []
with open(SRC, newline="", encoding="utf-8-sig") as fh:
    r = csv.DictReader(fh)
    for row in r:
        rows.append(row)

# normalize keys
def get(row, *cands):
    for c in cands:
        if c in row:
            return row[c]
    return ""

METRICS = ["spend","value","purch","lpv","atc","co"]
def blank():
    return {m:0.0 for m in METRICS}

def add(acc, row):
    acc["spend"] += f(get(row,"Amount spent (USD)"))
    acc["value"] += f(get(row,"Purchases conversion value"))
    acc["purch"] += f(get(row,"Purchases"))
    acc["lpv"]   += f(get(row,"Landing page views"))
    acc["atc"]   += f(get(row,"Adds to cart"))
    acc["co"]    += f(get(row,"Checkouts initiated"))

overall = blank()
by_campaign = defaultdict(blank)
by_adset = defaultdict(blank)
by_ad = defaultdict(blank)         # full ad name
by_creative = defaultdict(blank)   # creative base (strip _Mon_DD_LP suffix)
by_lp = defaultdict(blank)         # landing page token
by_product = defaultdict(blank)
days = set()

# map adset -> campaign, lp label
adset_campaign = {}
adset_lp = {}
creative_variants = defaultdict(set)

def parse_lp_from_adset(adset):
    # e.g. "Luna Naturals_Adv get.lunanaturals.co/articles/deet-switch_Mosquito Patch for Kids_23Jun26"
    # or "Luna Naturals_PDP get.lunanaturals.co_Mosquito Patch for Kids_23Jun26"
    m = re.search(r"_(PDP|Adv|Listicle|UGC|Static|TSL|Animation|getlunanatural[^_]*|[A-Za-z]+)\s+([^_]+)_", adset)
    # fallback: grab the url-ish chunk
    urlm = re.search(r"(get\.?lunanatural[^_]*|getlunanatural[^_]*)", adset)
    return urlm.group(1) if urlm else adset

def lp_type(adset):
    for t in ["PDP","Adv","Listicle","UGC","Static","TSL","Animation","New PDP"]:
        if re.search(r"_%s " % re.escape(t), adset) or ("_"+t+"_") in adset:
            return t
    if "getlunanatural.co/lunanaturals/kids" in adset:
        return "New PDP"
    return "Other"

def creative_base(ad):
    # strip trailing _Mon_DD_LP and _Jun_23_... style suffixes
    b = re.sub(r"_?(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)_\d{1,2}_.*$", "", ad)
    return b.strip("_") or ad

def product_of(row):
    name = get(row,"Campaign name") + get(row,"Ad set name")
    if "Bug Tick Repellent Spray" in name or "tick" in name.lower():
        return "Bug/Tick Repellent Spray"
    return "Mosquito Patch for Kids"

for row in rows:
    add(overall, row)
    camp = get(row,"Campaign name")
    adset = get(row,"Ad set name")
    ad = get(row,"Ad name")
    day = get(row,"Day")
    days.add(day)
    add(by_campaign[camp], row)
    add(by_adset[adset], row)
    add(by_ad[ad], row)
    cb = creative_base(ad)
    add(by_creative[cb], row)
    creative_variants[cb].add(ad)
    add(by_lp[parse_lp_from_adset(adset)+" | "+lp_type(adset)], row)
    add(by_product[product_of(row)], row)
    adset_campaign[adset] = camp
    adset_lp[adset] = (parse_lp_from_adset(adset), lp_type(adset))

def enrich(d):
    out = {}
    for k,v in d.items():
        v = dict(v)
        v["roas"] = round(v["value"]/v["spend"],2) if v["spend"]>0 else 0
        v["cpa"] = round(v["spend"]/v["purch"],2) if v["purch"]>0 else None
        v["aov"] = round(v["value"]/v["purch"],2) if v["purch"]>0 else None
        v["cvr"] = round(100*v["purch"]/v["lpv"],2) if v["lpv"]>0 else 0
        v["cpc_lpv"] = round(v["spend"]/v["lpv"],2) if v["lpv"]>0 else None
        for m in METRICS: v[m]=round(v[m],2)
        out[k]=v
    return out

result = {
  "overall": enrich({"all":overall})["all"],
  "days": sorted(d for d in days if d),
  "by_campaign": enrich(by_campaign),
  "by_adset": enrich(by_adset),
  "by_ad": enrich(by_ad),
  "by_creative": enrich(by_creative),
  "by_lp": enrich(by_lp),
  "by_product": enrich(by_product),
  "adset_campaign": adset_campaign,
  "adset_lp": {k:list(v) for k,v in adset_lp.items()},
  "creative_variants": {k:sorted(v) for k,v in creative_variants.items()},
  "row_count": len(rows),
}

with open("/Users/sproutoffice/luna-naturals-report/data/agg.json","w") as fh:
    json.dump(result, fh, indent=2)

# ---- print summary ----
o = result["overall"]
print(f"ROWS: {len(rows)}  DAYS: {result['days'][0]}..{result['days'][-1]}")
print(f"OVERALL spend=${o['spend']} value=${o['value']} purch={o['purch']} roas={o['roas']} cpa={o['cpa']} aov={o['aov']} lpv={o['lpv']} atc={o['atc']} co={o['co']} cvr={o['cvr']}%")
print("\n== BY PRODUCT ==")
for k,v in sorted(result["by_product"].items(), key=lambda x:-x[1]["spend"]):
    print(f"  {k:32s} spend=${v['spend']:>8} purch={v['purch']:>4} value=${v['value']:>8} roas={v['roas']}")
print("\n== BY CAMPAIGN (spend desc) ==")
for k,v in sorted(result["by_campaign"].items(), key=lambda x:-x[1]["spend"]):
    print(f"  spend=${v['spend']:>8} roas={v['roas']:>5} purch={v['purch']:>4} cpa={v['cpa']} value=${v['value']:>8} cvr={v['cvr']}% | {k}")
print("\n== BY LP (spend desc) ==")
for k,v in sorted(result["by_lp"].items(), key=lambda x:-x[1]["spend"]):
    print(f"  spend=${v['spend']:>8} roas={v['roas']:>5} purch={v['purch']:>4} lpv={v['lpv']:>5} cvr={v['cvr']:>5}% co={v['co']} | {k}")
print("\n== TOP CREATIVES (spend desc, top 25) ==")
for k,v in sorted(result["by_creative"].items(), key=lambda x:-x[1]["spend"])[:25]:
    print(f"  spend=${v['spend']:>8} roas={v['roas']:>5} purch={v['purch']:>4} lpv={v['lpv']:>5} value=${v['value']:>8} | {k}")
print("\n== CREATIVES WITH PURCHASES ==")
for k,v in sorted(result["by_creative"].items(), key=lambda x:-x[1]["purch"]):
    if v["purch"]>0:
        print(f"  purch={v['purch']:>4} roas={v['roas']:>5} spend=${v['spend']:>8} value=${v['value']:>8} | {k}")
