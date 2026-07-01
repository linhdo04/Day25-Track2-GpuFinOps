"""M2 — Inference Cost Levers: $/1M-token, batch x cache x cascade (deck §7).

Run: python missions/m2_inference_levers.py
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from collections import Counter
from missions._common import load_csv, num
from finops import pricing, sustainability

# $/1M tokens (input, output) — illustrative 2026.
MODEL_PRICES = {"small": (0.20, 0.40), "large": (3.00, 15.00)}
CACHE_WRITE_COST = 1.25
CACHE_READ_DISCOUNT = 0.10
REASONING_TRAFFIC_CAP = 0.05


def run(verbose: bool = True) -> dict:
    rows = load_csv("token_usage.csv")
    base_cost = cascade_cost = cache_cost = opt_cost = 0.0
    total_tokens = 0
    reasoning_cost = standard_cost = 0.0
    reasoning_wh = standard_wh = 0.0
    reasoning_count = 0

    # A team shares a stable system-prompt cache namespace.  Count observed
    # cacheable requests as the conservative expected reuse for that namespace.
    cache_reads = Counter(r["team"] for r in rows if int(num(r["cached_input_tokens"])) > 0)
    cache_enabled = {
        team: pricing.cache_is_worth_it(reads, CACHE_WRITE_COST, CACHE_READ_DISCOUNT)
        for team, reads in cache_reads.items()
    }
    reasoning_deltas = []
    reasoning_energy_deltas = []
    for r in rows:
        inp, out = int(num(r["input_tokens"])), int(num(r["output_tokens"]))
        cached = int(num(r["cached_input_tokens"]))
        is_batch = bool(int(num(r["is_batch"])))
        total_tokens += inp + out
        # BASELINE: naive deployment — everything on the large model, no cache, no batch
        lin, lout = MODEL_PRICES["large"]
        base_cost += pricing.request_cost(inp, out, lin, lout)
        # Measure each lever sequentially so its contribution remains auditable.
        pin, pout = MODEL_PRICES[r["route_tier"]]
        cascade_cost += pricing.request_cost(inp, out, pin, pout)
        eligible_cached = cached if cache_enabled.get(r["team"], False) else 0
        cached_request_cost = pricing.request_cost(inp, out, pin, pout, cached_in=eligible_cached)
        cache_cost += cached_request_cost
        optimized_request_cost = pricing.request_cost(
            inp, out, pin, pout, cached_in=eligible_cached, batch=is_batch
        )
        opt_cost += optimized_request_cost

        is_reasoning = bool(int(num(r["is_reasoning"])))
        wh = sustainability.wh_per_query(inp + out, is_reasoning=is_reasoning)
        if is_reasoning:
            reasoning_count += 1
            reasoning_cost += optimized_request_cost
            reasoning_wh += wh
            normal_out = max(1, out // 6)  # generator applies a 6x output-token reasoning tax
            normal_cost = pricing.request_cost(
                inp, normal_out, pin, pout, cached_in=eligible_cached, batch=is_batch
            )
            normal_wh = sustainability.wh_per_query(inp + normal_out)
            reasoning_deltas.append(optimized_request_cost - normal_cost)
            reasoning_energy_deltas.append(wh - normal_wh)
        else:
            standard_cost += optimized_request_cost
            standard_wh += wh

    base_pm = pricing.dollars_per_million(base_cost, total_tokens)
    opt_pm = pricing.dollars_per_million(opt_cost, total_tokens)
    savings_pct = (1 - opt_cost / base_cost) * 100 if base_cost else 0.0
    lever_savings = {
        "cascade": base_cost - cascade_cost,
        "cache": cascade_cost - cache_cost,
        "batch": cache_cost - opt_cost,
    }
    reasoning_share = reasoning_count / len(rows) if rows else 0.0
    target_reasoning = int(len(rows) * REASONING_TRAFFIC_CAP)
    avoided_reasoning = max(0, reasoning_count - target_reasoning)
    cap_savings = (
        sum(reasoning_deltas) / len(reasoning_deltas) * avoided_reasoning
        if reasoning_deltas else 0.0
    )
    cap_wh_savings = (
        sum(reasoning_energy_deltas) / len(reasoning_energy_deltas) * avoided_reasoning
        if reasoning_energy_deltas else 0.0
    )

    if verbose:
        print("== M2 Inference Cost Levers ==")
        print(f"requests={len(rows)}  tokens={total_tokens:,}")
        print(f"baseline  : ${base_cost:,.2f}/day   ${base_pm:.3f}/1M-token")
        print(f"optimized : ${opt_cost:,.2f}/day   ${opt_pm:.3f}/1M-token")
        print(f"savings   : {savings_pct:.1f}%  (cascade + caching + batch)")
        print("lever savings/day: " + ", ".join(f"{k}=${v:,.2f}" for k, v in lever_savings.items()))
        print(f"discount stack (batch + 100% cache): {pricing.discount_stack(batch=True, cache_hit_frac=1.0):.3f} of naive")
        break_even = pricing.cache_break_even_reads(CACHE_WRITE_COST, CACHE_READ_DISCOUNT)
        print(f"cache break-even: >{break_even:.2f} reads; enabled teams={sorted(k for k, v in cache_enabled.items() if v)}")
        print(f"reasoning: {reasoning_count}/{len(rows)} requests ({reasoning_share:.1%}), "
              f"${reasoning_cost:,.2f}/day, {reasoning_wh:,.0f} Wh/day")
        print(f"cap reasoning at {REASONING_TRAFFIC_CAP:.0%}: save ${cap_savings:,.2f}/day and {cap_wh_savings:,.0f} Wh/day")

    return {
        "baseline_daily": round(base_cost, 2), "optimized_daily": round(opt_cost, 2),
        "baseline_per_m": round(base_pm, 3), "optimized_per_m": round(opt_pm, 3),
        "savings_pct": round(savings_pct, 1), "total_tokens": total_tokens,
        "lever_savings_daily": {k: round(v, 2) for k, v in lever_savings.items()},
        "cache_break_even_reads": round(pricing.cache_break_even_reads(CACHE_WRITE_COST, CACHE_READ_DISCOUNT), 2),
        "cache_reads_by_team": dict(cache_reads),
        "cache_enabled_teams": sorted(k for k, v in cache_enabled.items() if v),
        "reasoning": {
            "requests": reasoning_count,
            "traffic_pct": round(reasoning_share * 100, 1),
            "cost_daily": round(reasoning_cost, 2),
            "cost_share_pct": round(reasoning_cost / opt_cost * 100, 1) if opt_cost else 0.0,
            "wh_daily": round(reasoning_wh, 2),
            "energy_share_pct": round(reasoning_wh / (reasoning_wh + standard_wh) * 100, 1) if reasoning_wh + standard_wh else 0.0,
            "cap_pct": REASONING_TRAFFIC_CAP * 100,
            "cap_savings_daily": round(cap_savings, 2),
            "cap_wh_savings_daily": round(cap_wh_savings, 2),
        },
    }


if __name__ == "__main__":
    run()
