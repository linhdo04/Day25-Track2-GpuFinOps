# Lab 25 — Submission Notes

The analysis prioritizes unit economics over hourly GPU price. The measured
inference cost falls from $6.488 to $1.126 per million
tokens. Cascade routing is the dominant inference lever; cache and batch add
incremental savings after the routing decision.

Two extensions are implemented and tested: cache break-even gating and a
reasoning budget. Cache is enabled only when expected reuse exceeds
1.39 reads. Reasoning represents 8.4% of requests
but 94.0% of energy, so routing it only for tasks with an
explicit complexity signal is the immediate governance action.

The infrastructure actions are to use spot for checkpointable jobs, reserved
capacity for steady workloads, remove idle capacity, and investigate low-MFU
GPUs before committing to expensive accelerators. The lowest-carbon region is
europe-north1; deployment still requires latency and data-residency checks.
