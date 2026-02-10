# Specs

This folder contains *declarative* specifications used by the pipeline:

- `spec/metrics_v1.yaml`: v1 metric registry for the initial scoreboard (base series + transforms + term aggregations).
- `spec/metrics_rationale.md`: human-readable rationale for key measurement choices (why these series, transforms, and aggregations).
- `spec/aggregation_kinds_v1.yaml`: formal semantics of `term_aggregation.kind` (so the engine is implementable/testable).
- `spec/attribution_v1.yaml`: formal semantics of time attribution / boundary rules (so "start/end" are deterministic).

Design goals:
- Make metric definitions explicit and reviewable in git.
- Keep results reproducible from online sources by recording upstream ids/URLs and caching raw downloads.
- Avoid silently changing definitions: if a metric changes meaningfully, add a new metric id (or a new spec version).
