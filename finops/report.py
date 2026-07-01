"""Report assembly — the lab's deliverable: baseline vs optimized + savings chart."""
from __future__ import annotations


def build_report(baseline_usd: float, optimized_usd: float, levers: dict,
                 sustainability: dict | None = None, period: str = "monthly",
                 unit_economics: dict | None = None,
                 analysis: dict | None = None) -> str:
    """Return a markdown cost-optimization report."""
    savings = baseline_usd - optimized_usd
    pct = (savings / baseline_usd * 100.0) if baseline_usd > 0 else 0.0
    lines = [
        "# NimbusAI — GPU Cost Optimization Report",
        "",
        f"**Period:** {period}  ",
        f"**Baseline spend:** ${baseline_usd:,.0f}  ",
        f"**Optimized spend:** ${optimized_usd:,.0f}  ",
        f"**Projected savings:** ${savings:,.0f}  (**{pct:.0f}%**)",
        "",
        "## Savings by lever",
        "",
        "| Lever | Savings (USD) |",
        "|---|---|",
    ]
    for name, amount in levers.items():
        lines.append(f"| {name} | ${amount:,.0f} |")
    if unit_economics:
        before = unit_economics.get("baseline_per_m", 0)
        after = unit_economics.get("optimized_per_m", 0)
        reduction = (1 - after / before) * 100 if before else 0.0
        lines += [
            "",
            "## Inference unit economics",
            "",
            "| Metric | Baseline | Optimized | Reduction |",
            "|---|---:|---:|---:|",
            f"| $/1M-token | ${before:.3f} | ${after:.3f} | {reduction:.1f}% |",
            "",
            "### Inference savings breakdown",
            "",
            "| Lever | Savings (USD/day) |",
            "|---|---:|",
        ]
        for name, amount in unit_economics.get("lever_savings_daily", {}).items():
            lines.append(f"| {name.title()} | ${amount:,.2f} |")
    if analysis:
        lies = analysis.get("util_lies", [])
        cache = analysis.get("cache", {})
        reasoning = analysis.get("reasoning", {})
        lines += [
            "",
            "## Technical findings",
            "",
            f"- **GPU-Util lie:** {', '.join(lies) or 'none'}. A busy GPU clock does not imply useful model FLOPs; memory stalls, I/O waits, and kernel-launch overhead can keep GPU-Util high while MFU remains below 30%. Cost decisions therefore use MFU/MBU, not GPU-Util alone.",
            f"- **Cache economics:** a 1.25x cache write and 0.10x cache read break even above {cache.get('break_even_reads', 0):.2f} repeated reads. The measured reuse enables caching for {', '.join(cache.get('enabled_teams', []))}.",
            f"- **Reasoning budget:** reasoning is {reasoning.get('traffic_pct', 0):.1f}% of traffic but {reasoning.get('cost_share_pct', 0):.1f}% of optimized inference cost and {reasoning.get('energy_share_pct', 0):.1f}% of serving energy. Capping it at {reasoning.get('cap_pct', 0):.0f}% saves ${reasoning.get('cap_savings_daily', 0):.2f}/day and {reasoning.get('cap_wh_savings_daily', 0):,.0f} Wh/day.",
            "",
            "## Prioritized actions",
            "",
            "1. Apply cascade routing first; it has the largest measured inference ROI.",
            "2. Enforce the reasoning cap and require an explicit complexity signal before routing to reasoning mode.",
            "3. Enable prompt caching only for namespaces above the measured reuse break-even, then batch latency-tolerant evaluation traffic.",
            "4. Move checkpointable jobs to spot, reserve steady workloads, right-size low-MFU GPUs, and terminate idle capacity.",
        ]
    if sustainability:
        lines += [
            "",
            "## Sustainability",
            "",
            f"- Energy per query: {sustainability.get('wh_per_query', 0):.2f} Wh",
            f"- Carbon per query: {sustainability.get('carbon_g', 0):.3f} gCO2e",
            f"- Lowest-carbon region: {sustainability.get('best_region', 'n/a')}",
            f"- Lowest-electricity-price region: {sustainability.get('cheapest_region', 'n/a')}",
            f"- Carbon avoided vs us-east-1: {sustainability.get('carbon_avoided_g', 0):.3f} gCO2e/query",
            "- Region choice must also satisfy data residency and user-latency requirements; carbon and electricity price alone are not sufficient.",
        ]
    lines += ["", "_Figures are June-2026 as-of snapshots; re-baseline before acting._"]
    return "\n".join(lines)


def savings_waterfall(levers: dict, path: str) -> str:
    """Write a simple savings bar chart PNG. Returns the path. No-op if matplotlib absent."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return ""
    names = list(levers.keys())
    vals = [levers[n] for n in names]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(names, vals, color="#2e548a")
    ax.set_ylabel("Savings (USD / month)")
    ax.set_title("GPU cost savings by FinOps lever")
    plt.xticks(rotation=20, ha="right")
    plt.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return path
