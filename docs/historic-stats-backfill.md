# Historic Stats Backfill

`historic-stats-backfill` is the manual job used to rebuild one or more metrics from `trii-prod-current-snapshots` into `trii-prod-historic-stats`.

It exists for one operational scenario: a metric formula is already derivable from historical raw snapshots, but that metric was not previously persisted in `historic-stats`.

## Why this job exists

- `current-snapshots` is already the deduplicated raw source of truth.
- `historic-stats-updater` should remain focused on live incremental updates.
- A historical rebuild for new metrics should be explicit, manual, and isolated from the live stream.

## Safe rollout for a new metric

1. Add the new formula to:
   - `infra/prod/services/lambda/historic-stats-updater/src/snapshot_metrics.py`
   - `infra/prod/services/lambda/historic-stats-backfill/src/snapshot_metrics.py`
2. Do **not** add the metric to `local.enabled_statistical_metrics` yet.
3. Deploy Terraform.
4. Run `historic-stats-backfill` in preview mode first with `apply=false`.
5. Validate the returned `snapshots_read`, `stat_items_rebuilt`, and the written metric rows you expect.
6. Run the same payload with `apply=true`.
7. Validate the resulting rows in `trii-prod-historic-stats`.
8. Only after validation, add the metric to `local.enabled_statistical_metrics`.
9. Deploy Terraform again so `historic-stats-updater` starts maintaining that metric in real time.

This sequence avoids changing the live updater before the historical baseline is complete.

## Event contract

The Lambda is manual and expects a JSON event.

Required:

- `metric_names`: list of metric keys to rebuild

Optional:

- `apply`: `false` by default; when `true`, the Lambda writes to `historic-stats`
- `symbols`: list of uppercase symbols; omit to scan all symbols
- `captured_at_from`: ISO-8601 timestamp with timezone
- `captured_at_to`: ISO-8601 timestamp with timezone

## Preview example

```json
{
  "apply": false,
  "metric_names": ["obi_l1", "obi_top_5"],
  "symbols": ["NUCO", "ISA"],
  "captured_at_from": "2026-08-01T00:00:00-05:00",
  "captured_at_to": "2026-08-20T23:59:59-05:00"
}
```

## Apply example

```json
{
  "apply": true,
  "metric_names": ["obi_l1", "obi_top_5"],
  "symbols": ["NUCO", "ISA"],
  "captured_at_from": "2026-08-01T00:00:00-05:00",
  "captured_at_to": "2026-08-20T23:59:59-05:00"
}
```

## AWS CLI invocation

Replace the payload file as needed:

```powershell
aws lambda invoke `
  --function-name trii-prod-historic-stats-backfill `
  --payload fileb://payload.json `
  response.json
```

Then inspect `response.json`.

## Operational guidance

- Prefer backfilling **specific symbols** first when validating a new metric.
- Prefer backfilling **time windows** for large histories instead of one huge all-time run.
- This job overwrites only the `(pk=symbol, sk=metric)` pairs you request.
- It does not touch `data_quality#yyyy-mm-dd` records.
- It does not require extra deduplication because `current-snapshots` is already the accepted raw source.

## Current live-enabled metrics

At the moment the live updater keeps these metrics:

- `spread_bps`
- `obi_l1`
- `obi_top_5`
- `book_pressure_ratio`
- `depth_weighted_microprice_deviation`
