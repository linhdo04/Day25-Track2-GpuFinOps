"""M5 — Optimization Report: combine M1-M4 into baseline-vs-optimized (deck §1/§11).

Run: python missions/m5_report.py   ->  outputs/report.md + outputs/savings.png
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import os
from missions._common import num, catalog_by_type, ROOT
from finops import report, sustainability
from missions import m1_efficiency_audit, m2_inference_levers, m3_purchasing

DAYS = 30
# one tier down for over-provisioned ("util-lie") GPUs
RIGHTSIZE_MAP = {"H100": "A100", "H200": "H100", "A100": "A10G", "A10G": "L4", "L4": "L4"}


def run(verbose: bool = True) -> dict:
    r1 = m1_efficiency_audit.run(verbose=False)
    r2 = m2_inference_levers.run(verbose=False)
    r3 = m3_purchasing.run(verbose=False)
    cat = catalog_by_type()

    # --- buckets ---
    infer_savings = (r2["baseline_daily"] - r2["optimized_daily"]) * DAYS
    purchasing_savings = r3["on_demand_monthly"] - r3["optimized_monthly"]

    idle_savings = r1["idle_waste_daily"] * DAYS
    rightsize_savings = 0.0
    for lie in r1["lies"]:
        cur = lie["gpu_type"]
        tgt = RIGHTSIZE_MAP.get(cur, cur)
        delta = num(cat[cur]["on_demand_hr"]) - num(cat[tgt]["on_demand_hr"])
        rightsize_savings += max(0.0, delta) * 24 * DAYS

    levers = {
        "Inference (cascade/cache/batch)": round(infer_savings),
        "Purchasing (spot/reserved)": round(purchasing_savings),
        "Right-size util-lies": round(rightsize_savings),
        "Kill idle GPUs": round(idle_savings),
    }
    baseline = r2["baseline_daily"] * DAYS + r3["on_demand_monthly"]
    optimized = baseline - sum(levers.values())
    total_pct = sum(levers.values()) / baseline * 100 if baseline else 0.0

    # --- sustainability snapshot ---
    median_tokens = 800
    wh = sustainability.wh_per_query(median_tokens)
    sust = {
        "wh_per_query": wh,
        "carbon_g": sustainability.carbon_g(wh, "us-east-1"),
        "best_region": min(sustainability.REGION_CARBON, key=sustainability.REGION_CARBON.get),
        "cheapest_region": min(sustainability.REGION_PRICE_KWH, key=sustainability.REGION_PRICE_KWH.get),
    }
    sust["carbon_avoided_g"] = sust["carbon_g"] - sustainability.carbon_g(wh, sust["best_region"])

    analysis = {
        "util_lies": [f"{x['gpu_id']} (MFU={x['mfu']:.1%})" for x in r1["lies"]],
        "cache": {
            "break_even_reads": r2["cache_break_even_reads"],
            "enabled_teams": r2["cache_enabled_teams"],
        },
        "reasoning": r2["reasoning"],
    }
    md = report.build_report(
        baseline, optimized, levers, sustainability=sust,
        unit_economics={
            "baseline_per_m": r2["baseline_per_m"],
            "optimized_per_m": r2["optimized_per_m"],
            "lever_savings_daily": r2["lever_savings_daily"],
        },
        analysis=analysis,
    )
    out_md = os.path.join(ROOT, "outputs", "report.md")
    os.makedirs(os.path.dirname(out_md), exist_ok=True)
    with open(out_md, "w") as f:
        f.write(md)
    writeup = """# Lab 25 — Submission Notes

The analysis prioritizes unit economics over hourly GPU price. The measured
inference cost falls from ${baseline_pm:.3f} to ${optimized_pm:.3f} per million
tokens. Cascade routing is the dominant inference lever; cache and batch add
incremental savings after the routing decision.

Two extensions are implemented and tested: cache break-even gating and a
reasoning budget. Cache is enabled only when expected reuse exceeds
{cache_be:.2f} reads. Reasoning represents {reasoning_traffic:.1f}% of requests
but {reasoning_energy:.1f}% of energy, so routing it only for tasks with an
explicit complexity signal is the immediate governance action.

The infrastructure actions are to use spot for checkpointable jobs, reserved
capacity for steady workloads, remove idle capacity, and investigate low-MFU
GPUs before committing to expensive accelerators. The lowest-carbon region is
{best_region}; deployment still requires latency and data-residency checks.
""".format(
        baseline_pm=r2["baseline_per_m"], optimized_pm=r2["optimized_per_m"],
        cache_be=r2["cache_break_even_reads"],
        reasoning_traffic=r2["reasoning"]["traffic_pct"],
        reasoning_energy=r2["reasoning"]["energy_share_pct"],
        best_region=sust["best_region"],
    )
    with open(os.path.join(ROOT, "outputs", "writeup.md"), "w") as f:
        f.write(writeup)
    png = report.savings_waterfall(levers, os.path.join(ROOT, "outputs", "savings.png"))

    if verbose:
        print("== M5 Optimization Report ==")
        print(md)
        print(f"\nWritten: outputs/report.md" + (f" + outputs/savings.png" if png else " (matplotlib absent: PNG skipped)"))

    return {"baseline_monthly": round(baseline), "optimized_monthly": round(optimized),
            "levers": levers, "total_savings_pct": round(total_pct, 1)}


if __name__ == "__main__":
    run()
