"""Published term prices -- catalog.

Every row is a price a seller publishes for committing to a length of time:
reserved instances, savings plans, committed-use discounts, capacity blocks,
calendar reservations, monthly/annual contracts. Read by hand from each
seller's public price list or keyless price API on TERM_CATALOG_AS_OF; the
source URL is on every row. Nothing here is estimated -- where a seller
publishes a figure in another unit (a VM per hour, a whole reservation term, a
discount off its own on-demand) the row keeps the published figure and the
arithmetic that turns it into $/GPU-hour.

Who is in the panel. A seller appears only if it publishes at least one term
price, and its on-demand rate is included only alongside that term price, so
every seller's term discount is measured against its own on-demand -- the same
matched-provider rule the tech-decay estimate uses. Sellers that publish no
term price (CoreWeave "up to 60%", Nebius "up to 35%", Crusoe, OCI, ...) are
not in this catalog; they are "contact sales" for anything but on-demand.

Left out on purpose, and why:
  * RunPod's GraphQL term fields (threeMonthPrice, sixMonthPrice, oneYearPrice)
    equal Secure on-demand for every GPU here; they are not a discount.
  * Vast.ai reserved discounts are set per host and per offer, and most
    H100/H200/B200/B300 hosts offer none. That needs a live adapter, not a
    catalog row.
  * TensorDock's H100 term table is undated and contradicts its own spot
    price; Hyperstack and Vultr "starting from" reserved prices state no term.
  * Rows whose form factor is not stated (e.g. "A100 80GB" 1x) unless they are
    sold as an 8-GPU node -- a 1x card may be PCIe, which the Fix excludes.
  * Prices published only in INR (Yotta).

Cluster products (Lambda 1-Click Clusters, Together's H200/B200 reserved
clusters of 256+ GPUs) are kept with their minimum size. Term pricing covers a
single node and excludes them, but they are the only public cluster-size
tiers, so they stay on record.
"""

from __future__ import annotations
import re
from typing import Any, Dict, List, Optional, Tuple

TERM_CATALOG_AS_OF = "2026-09-27"

OD = (0, 0)
M1, M3, M6 = (30, 30), (90, 90), (180, 180)
Y1, Y2, Y3, Y5 = (365, 365), (730, 730), (1095, 1095), (1825, 1825)
TERM_HOURS = {365: 8760, 1095: 26280, 1825: 43800}

AWS_EC2 = "https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/us-east-1/index.csv"
AWS_SP = "https://pricing.us-east-1.amazonaws.com/savingsPlan/v1.0/aws/AWSComputeSavingsPlan/current/region_index.json"
AWS_CB = "https://aws.amazon.com/ec2/capacityblocks/pricing/"
AZURE = "https://prices.azure.com/api/retail/prices"
GCP = "https://cloud.google.com/products/compute/pricing/accelerator-optimized"
GCP_DWS = "https://cloud.google.com/products/dws/pricing"
TOGETHER = "https://www.together.ai/pricing"
VERDA = "https://api.verda.com/v1/long-term/periods"
HYPERBOLIC = "https://api.hyperbolic.xyz/v2/on-demand/reserve-options"
CIVO = "https://www.civo.com/pricing"
GCORE = "https://gcore.com/pricing/ai"
JARVIS = "https://jarvislabs.ai/pricing"
DO = "https://www.digitalocean.com/pricing/gpu-droplets"
PAPERSPACE = "https://www.paperspace.com/pricing"
CIRRASCALE = "https://www.cirrascale.com/pricing"
LATITUDE = "https://www.latitude.sh/pricing"
LAMBDA = "https://lambda.ai/pricing"


def per_instance_hour(price: float, gpus: int) -> Dict[str, Any]:
    return {"per_gpu": price / gpus, "published": f"${price:,.4f} per instance-hour", "math": f"{price:g} / {gpus} GPUs"}


def per_gpu_hour(price: float) -> Dict[str, Any]:
    return {"per_gpu": price, "published": f"${price:.4f} per GPU-hour", "math": "as published"}


def whole_term(total: float, days: int, gpus: int) -> Dict[str, Any]:
    hours = TERM_HOURS[days]
    return {"per_gpu": total / hours / gpus, "published": f"${total:,.2f} per VM for the whole term",
            "math": f"{total:g} / {hours} h / {gpus} GPUs"}


def discount_off(od_per_gpu: float, pct: float) -> Dict[str, Any]:
    return {"per_gpu": od_per_gpu * (1 - pct / 100), "published": f"{pct:g}% off on-demand ${od_per_gpu:g}/GPU-hr",
            "math": f"{od_per_gpu:g} x (1 - {pct / 100:g})"}


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def quote(provider: str, segment: str, family: str, instance: str, option: str, days: Tuple[int, int],
          price: Dict[str, Any], source: str, *, gpus: int = 8, min_gpus: Optional[int] = None,
          form_factor: str = "HGX 8x", region: str = "", notes: Optional[str] = None) -> Dict[str, Any]:
    min_gpus = min_gpus or gpus
    lo, hi = days
    qid = f"{_slug(provider)}_{family.lower()}_{lo}-{hi}" + (f"_{min_gpus}g" if min_gpus > 8 else "")
    return {
        "id": qid, "provider": provider, "segment": segment, "family": family, "instance": instance,
        "option": option, "min_days": lo, "max_days": hi, "gpus": gpus, "min_gpus": min_gpus,
        "form_factor": form_factor, "per_gpu": round(price["per_gpu"], 4), "published": price["published"],
        "math": price["math"], "region": region, "source": source, "captured": TERM_CATALOG_AS_OF, "notes": notes,
    }


def _hyperscaler() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    H = "hyperscaler"

    # AWS us-east-1. Price List bulk files published 2026-09-25; Capacity Blocks
    # page Last-Modified 2026-09-25. The lowest no-upfront commitment per term:
    # EC2 Instance Savings Plan (== Standard RI), or Compute Savings Plan where
    # AWS publishes no Instance plan for that term. Capacity Blocks: one rate for
    # any length from 1 to 182 days, paid upfront, reset by AWS "regularly".
    aws = [
        ("A100", "p4de.24xlarge", 27.44705, 17.712, 17.40137, "EC2 Instance Savings Plan", 11.71777),
        ("H100", "p5.48xlarge", 55.04, 41.528, 34.6752, "EC2 Instance Savings Plan", 23.77728),
        ("H200", "p5en.48xlarge", 63.296, 54.920, 39.87648, "EC2 Instance Savings Plan", 27.34387),
        ("B200", "p6-b200.48xlarge", 113.9328, 98.84, 89.72208, "Compute Savings Plan", 49.21897),
        ("B300", "p6-b300.48xlarge", 142.416, 112.32, 112.1526, "Compute Savings Plan", 61.52371),
    ]
    for fam, inst, od, cb, y1, y1_plan, y3 in aws:
        kw = {"region": "us-east-1"}
        out.append(quote("AWS", H, fam, inst, "On-Demand", OD, per_instance_hour(od, 8), AWS_EC2, **kw))
        out.append(quote("AWS", H, fam, inst, "EC2 Capacity Block (1-182 days)", (1, 182), per_instance_hour(cb, 8), AWS_CB, **kw,
                         notes="Flat rate for any block length; price is reset by AWS on supply and demand"))
        out.append(quote("AWS", H, fam, inst, f"{y1_plan}, 1yr, No Upfront", Y1, per_instance_hour(y1, 8), AWS_SP, **kw,
                         notes=None if y1_plan.startswith("EC2") else "AWS publishes no 1-year EC2 Instance Savings Plan or RI for this type"))
        out.append(quote("AWS", H, fam, inst, "EC2 Instance Savings Plan, 3yr, No Upfront", Y3, per_instance_hour(y3, 8), AWS_SP, **kw))

    # Azure Retail Prices API. A reservation's unitPrice is the whole term per VM
    # (the API labels it "1 Hour"); monthly and upfront payment cost the same.
    azure = [
        ("A100", "ND96amsr A100 v4", "eastus", 32.77, {365: 183722.0, 1095: 378926.0}),
        ("H100", "ND96isr H100 v5", "eastus", 98.32, {365: 551221.0, 1095: 1134310.0, 1825: 1722566.0}),
        ("H200", "ND96isr H200 v5", "eastus2", 84.8, {365: 407526.0, 1095: 1109592.0}),
    ]
    names = {365: "1 Year", 1095: "3 Years", 1825: "5 Years"}
    for fam, inst, region, od, terms in azure:
        out.append(quote("Azure", H, fam, inst, "Pay-as-you-go", OD, per_instance_hour(od, 8), AZURE, region=region))
        for days, total in terms.items():
            out.append(quote("Azure", H, fam, inst, f"Reserved VM Instance, {names[days]}", (days, days),
                             whole_term(total, days, 8), AZURE, region=region))

    # Google Cloud accelerator-optimized pricing page (A-series table states no
    # region; its values match the Americas SKUs, which cover us-central1) and
    # the DWS pricing page. Calendar mode reserves 1-90 days at one flat rate.
    # Resource CUDs are 1 or 3 years, billed monthly. A2 has no calendar mode
    # and a2-ultragpu-8g has no CUD price, so A100 80GB is the 1-GPU shape
    # (A2 prices scale linearly with GPU count).
    gcp = [
        ("A100", "a2-ultragpu-1g", 1, 5.06879789, None, 4.199690411, 3.499997559),
        ("H100", "a3-highgpu-8g", 8, 88.490000119, 41.60, 61.383674231, 38.864383195),
        ("H200", "a3-ultragpu-8g", 8, 84.806908493, 59.36, 58.471933151, 37.208420822),
        ("B200", "a4-highgpu-8g", 8, None, 90.22, 88.9272, 56.7072),
    ]
    for fam, inst, gpus, od, cal, y1, y3 in gcp:
        kw = {"gpus": gpus, "region": "us-central1", "form_factor": "SXM4 (1x)" if gpus == 1 else "HGX 8x"}
        if od is not None:
            out.append(quote("Google Cloud", H, fam, inst, "On-demand", OD, per_instance_hour(od, gpus), GCP, **kw,
                             notes="Google's docs say A3 Ultra is not generally available on-demand; the pricing page still lists this rate" if fam == "H200" else None))
        if cal is not None:
            out.append(quote("Google Cloud", H, fam, inst, "DWS Calendar mode (1-90 days)", (1, 90), per_instance_hour(cal, gpus), GCP_DWS, **kw))
        out.append(quote("Google Cloud", H, fam, inst, "Resource CUD, 1 year", Y1, per_instance_hour(y1, gpus), GCP, **kw))
        out.append(quote("Google Cloud", H, fam, inst, "Resource CUD, 3 years", Y3, per_instance_hour(y3, gpus), GCP, **kw))
    return out


def _neocloud() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    N = "neocloud"

    # Together AI -- GPU Clusters. Reserved tiers are 7-30, 31-90 and 91-180 days;
    # 181+ is "contact us". H200 and B200 reservations are sold as 256+ GPU clusters.
    together = [
        ("H100", 3.99, [(7, 30, 3.69), (31, 90, 3.45), (91, 180, 3.19)], 8),
        ("H200", 5.99, [(7, 30, 4.99), (31, 90, 4.15), (91, 180, 3.99)], 256),
        ("B200", 8.19, [(7, 30, 7.99), (31, 90, 7.79), (91, 180, 6.79)], 256),
        ("B300", 9.99, [], 8),
    ]
    for fam, od, tiers, reserve_min in together:
        out.append(quote("Together AI", N, fam, f"HGX {fam} cluster", "On-demand", OD, per_gpu_hour(od), TOGETHER,
                         notes="Promotional rate to 2026-09-30 (list $5.49)" if fam == "H100" else None))
        for lo, hi, p in tiers:
            out.append(quote("Together AI", N, fam, f"HGX {fam} cluster", f"Reserved, {lo}-{hi} days", (lo, hi), per_gpu_hour(p), TOGETHER,
                             min_gpus=reserve_min))

    # Verda (DataCrunch) -- keyless API: per-GPU on-demand is the same at 1-8x;
    # long-term periods publish a discount off it.
    verda_od = {"A100": ("A100 SXM4 80GB", 1.797), "H100": ("H100 SXM5", 3.555), "H200": ("H200 SXM5", 4.639),
                "B200": ("B200 SXM6", 6.85), "B300": ("B300 SXM6", 8.452)}
    verda_terms = [(M1, 2, "1 month"), (M3, 3, "3 months"), (M6, 4, "6 months"), (Y1, 8, "12 months"), (Y2, 25, "24 months")]
    for fam, (inst, od) in verda_od.items():
        out.append(quote("Verda", N, fam, inst, "On-demand", OD, per_gpu_hour(od), "https://api.verda.com/v1/instance-types", gpus=1, form_factor="SXM"))
        for days, pct, label in verda_terms:
            out.append(quote("Verda", N, fam, inst, f"Long-term, {label}", days, discount_off(od, pct), VERDA, gpus=1, form_factor="SXM"))

    # Hyperbolic -- keyless API: 7/14/30-day reservations at 1/3/5% off on-demand.
    out.append(quote("Hyperbolic", N, "H100", "H100 SXM5 VM", "On-demand", OD, per_gpu_hour(3.19),
                     "https://api.hyperbolic.xyz/v2/on-demand/rental-options", gpus=1, form_factor="SXM5", region="us-east-1"))
    out.append(quote("Hyperbolic", N, "H100", "H100 SXM5 VM", "Reservation, 30 days", M1, discount_off(3.19, 5), HYPERBOLIC,
                     gpus=1, form_factor="SXM5", region="us-east-1"))

    # Civo -- commitment tabs 6/12/24/36 months; same per-GPU price at 1x or 8x.
    civo = [
        ("H100", "H100 SXM", {OD: 2.99, M6: 2.79, Y1: 2.69, Y2: 2.59, Y3: 2.49}),
        ("H200", "H200 SXM", {OD: 3.49, M6: 3.29, Y1: 3.19, Y2: 3.09, Y3: 2.99}),
        ("B200", "B200 8x", {Y1: 4.49, Y2: 3.99, Y3: 3.79}),
        ("B300", "B300 8x", {OD: 7.49, Y1: 6.49, Y2: 5.99, Y3: 5.49}),
    ]
    for fam, inst, prices in civo:
        for days, p in prices.items():
            out.append(quote("Civo", N, fam, inst, "On-demand" if days == OD else f"Commitment, {days[0] // 30 if days[0] < 365 else days[0] // 365 * 12} months",
                             days, per_gpu_hour(p), CIVO, form_factor="SXM"))

    # Gcore -- 8x bare metal; the page shows EUR and the USD figure Gcore itself
    # publishes. USD used.
    gcore = [
        ("A100", "8x A100 SXM bare metal", {OD: 1.40, Y1: 1.15, Y3: 1.00}),
        ("H100", "8x H100 SXM bare metal", {OD: 2.50, Y1: 2.04, Y3: 1.93}),
        ("H200", "8x H200 SXM bare metal", {OD: 3.00, Y1: 2.30, Y3: 2.20}),
        ("B300", "8x B300 SXM bare metal", {OD: 6.60}),
    ]
    for fam, inst, prices in gcore:
        for days, p in prices.items():
            out.append(quote("Gcore", N, fam, inst, {OD: "On-demand", Y1: "Reserve 12 months", Y3: "Reserve 36 months"}[days],
                             days, per_gpu_hour(p), GCORE))

    # Jarvislabs -- 1/3/6/12-month plans; banner announces new H100/H200 rates from 2026-10-05.
    jarvis = [
        ("H100", "H100 SXM", {OD: 2.69, M1: 2.64, M3: 2.61, M6: 2.58, Y1: 2.47}),
        ("H200", "H200 SXM", {OD: 3.99, M1: 3.91, M3: 3.87, M6: 3.83, Y1: 3.67}),
    ]
    for fam, inst, prices in jarvis:
        for days, p in prices.items():
            label = "On-demand" if days == OD else f"{days[0] // 30 if days[0] < 365 else 12}-month plan"
            out.append(quote("Jarvislabs", N, fam, inst, label, days, per_gpu_hour(p), JARVIS, gpus=1, form_factor="SXM"))

    # DigitalOcean GPU Droplets -- "contractual commitment of 12 months"; new pricing effective 2026-08-01.
    for fam, od, y1, g in (("H100", 4.41, 3.26, 1), ("H200", 4.47, 3.40, 1), ("B300", None, 7.94, 8)):
        if od is not None:
            out.append(quote("DigitalOcean", N, fam, f"HGX {fam} Droplet", "On-demand", OD, per_gpu_hour(od), DO, gpus=g))
        out.append(quote("DigitalOcean", N, fam, f"HGX {fam} Droplet", "Reserved, 12-month commitment", Y1, per_gpu_hour(y1), DO, gpus=g))

    # Paperspace (DigitalOcean) -- separate price list. "$2.24/hour pricing is for a 3-year commitment".
    out.append(quote("Paperspace", N, "H100", "HGX H100", "On-demand", OD, per_gpu_hour(5.95), PAPERSPACE, gpus=1,
                     notes="Page marks this a special promo price"))
    out.append(quote("Paperspace", N, "H100", "HGX H100", "3-year commitment", Y3, per_gpu_hour(2.24), PAPERSPACE, gpus=1))

    # Cirrascale -- sells 8-GPU servers by the month only (no hourly on-demand).
    # The page prints each monthly price and its hourly equivalent; hourly used.
    cirrascale = [
        ("A100", "8x A100 80GB", [(M1, 18999, 3.25), (M3, 18049, 3.09), (M6, 17099, 2.93), (Y1, 15199, 2.60)]),
        ("H100", "8x H100 standalone", [(M1, 24999, 4.28), (M3, 23749, 4.07), (M6, 22499, 3.85), (Y1, 19999, 3.43)]),
        ("H200", "8x H200", [(M1, 26499, 4.54), (M3, 25179, 4.31), (M6, 23849, 4.08), (Y1, 21199, 3.63)]),
        ("B200", "8x B200 standalone", [(M1, 34999, 5.99), (M3, 33249, 5.69), (M6, 31499, 5.39), (Y1, 27999, 4.79)]),
    ]
    for fam, inst, rows in cirrascale:
        for days, monthly, hourly in rows:
            label = f"{days[0] // 30 if days[0] < 365 else 12}-month block"
            out.append(quote("Cirrascale", N, fam, inst, label, days,
                             {"per_gpu": hourly, "published": f"${monthly:,}/server-month, ${hourly:.2f}/GPU-hr equivalent", "math": "hourly equivalent as published"},
                             CIRRASCALE))

    # Latitude.sh -- g4.b300.large (8x HGX B300), hourly or prepaid monthly/annual.
    for days, label, p in ((OD, "Hourly", 128.00), (M1, "Monthly, prepaid", 64.00), (Y1, "Annual, prepaid", 44.80)):
        out.append(quote("Latitude.sh", N, "B300", "g4.b300.large", label, days, per_instance_hour(p, 8), LATITUDE))

    # Lambda 1-Click Clusters -- one price for any length from 2 weeks to 1 year,
    # tiered by cluster size. Multi-node products: kept for the record, excluded
    # from single-node term pricing.
    for fam, tiers in (("H100", [(16, 6.16), (64, 5.85), (256, 5.54)]), ("B200", [(16, 9.86), (64, 9.36), (256, 8.87)])):
        for size, p in tiers:
            out.append(quote("Lambda", N, fam, f"1-Click Cluster HGX {fam}", f"1-Click Cluster, {size}+ GPUs, 2 weeks - 1 year",
                             (14, 365), per_gpu_hour(p), LAMBDA, min_gpus=size))
    return out


TERM_QUOTES: List[Dict[str, Any]] = _hyperscaler() + _neocloud()

# Third-party term readings. Not seller quotes, so never part of a cell;
# shown beside the cell they describe.
TERM_REFERENCES: List[Dict[str, Any]] = [
    {"segment": "neocloud", "family": "H100", "term": "1Y", "low": 2.40, "high": 3.20,
     "label": "SemiAnalysis H100 1-year contract, 25th-75th percentile, Aug 2026",
     "source": "https://gpu-index.semianalysis.com/api/public-data", "captured": TERM_CATALOG_AS_OF},
]
