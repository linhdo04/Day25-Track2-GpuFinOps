# NimbusAI — GPU Cost Optimization Report

**Period:** monthly  
**Baseline spend:** $27,133  
**Optimized spend:** $14,626  
**Projected savings:** $12,507  (**46%**)

## Savings by lever

| Lever | Savings (USD) |
|---|---|
| Inference (cascade/cache/batch) | $1,212 |
| Purchasing (spot/reserved) | $10,040 |
| Right-size util-lies | $655 |
| Kill idle GPUs | $600 |

## Inference unit economics

| Metric | Baseline | Optimized | Reduction |
|---|---:|---:|---:|
| $/1M-token | $6.488 | $1.126 | 82.6% |

### Inference savings breakdown

| Lever | Savings (USD/day) |
|---|---:|
| Cascade | $37.40 |
| Cache | $1.20 |
| Batch | $1.79 |

## Technical findings

- **GPU-Util lie:** gpu-h100-4 (MFU=19.4%), gpu-a10g-1 (MFU=26.8%). A busy GPU clock does not imply useful model FLOPs; memory stalls, I/O waits, and kernel-launch overhead can keep GPU-Util high while MFU remains below 30%. Cost decisions therefore use MFU/MBU, not GPU-Util alone.
- **Cache economics:** a 1.25x cache write and 0.10x cache read break even above 1.39 repeated reads. The measured reuse enables caching for assistant, eval, rag, search.
- **Reasoning budget:** reasoning is 8.4% of traffic but 16.5% of optimized inference cost and 94.0% of serving energy. Capping it at 5% saves $0.41/day and 11,932 Wh/day.

## Prioritized actions

1. Apply cascade routing first; it has the largest measured inference ROI.
2. Enforce the reasoning cap and require an explicit complexity signal before routing to reasoning mode.
3. Enable prompt caching only for namespaces above the measured reuse break-even, then batch latency-tolerant evaluation traffic.
4. Move checkpointable jobs to spot, reserve steady workloads, right-size low-MFU GPUs, and terminate idle capacity.

## Sustainability

- Energy per query: 0.24 Wh
- Carbon per query: 0.091 gCO2e
- Lowest-carbon region: europe-north1
- Lowest-electricity-price region: us-east-wa
- Carbon avoided vs us-east-1: 0.084 gCO2e/query
- Region choice must also satisfy data residency and user-latency requirements; carbon and electricity price alone are not sufficient.

_Figures are June-2026 as-of snapshots; re-baseline before acting._