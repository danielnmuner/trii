# Historic Stats Backfill

`historic-stats-backfill` is the manual job used to rebuild one or more metrics from `trii-prod-current-snapshots` into `trii-prod-historic-stats`.

It exists for one operational scenario: a metric formula is already derivable from historical raw snapshots, but that metric was not previously persisted in `historic-stats`.

The current implementation is optimized for **statistical metric rows** such as `obi_l1` or `spread_bps`, where each accepted snapshot contributes exactly one scalar value into a Welford accumulator. A seasonality profile is different: it is a **new record type** with intraday buckets, delta reconstruction, and per-bucket state.

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

## When the change is a new record type instead of a new metric

Seasonality does **not** fit the current `metric_names -> one scalar per snapshot -> one stat row` contract.

Reasons:

- The current stat engine persists one row per `(symbol, metric)` and one Welford state for that metric.
- Seasonality requires reconstructing `delta_volume` and `delta_value` from **contiguous snapshots**.
- The result is not one scalar sample; it is a **weekly bucketed profile** by trading weekday and hour or half-hour slot.
- The normalized participation of a bucket depends on the **final total traded volume of that trading day**, so a fully correct `mu` and `sigma` for participation cannot be finalized until the session closes.

For that reason, seasonality should be documented and implemented as a **dedicated record type** and not as another entry inside `local.enabled_statistical_metrics`.

## Seasonality calculation logic

The seasonality profile is derived from cumulative market snapshots by converting them into flow deltas across contiguous captures:

- For each 30-second interval `n`, compute `delta_volume_n = volume_n - volume_{n-1}`.
- For each 30-second interval `n`, compute `delta_value_n = value_n - value_{n-1}`.
- Discard negative deltas, null intervals, and counter resets around market open or source restarts.
- Assign every valid delta to its trading date, weekday, and intraday bucket such as `09:00`, `09:30`, `10:00`, or the chosen session grain.
- Aggregate bucket totals within the day:
  - `bucket_volume = sum(delta_volume)`
  - `bucket_value = sum(delta_value)`
  - `bucket_vwap = bucket_value / bucket_volume`
  - `volume_rate = delta_volume / delta_seconds`
  - `value_rate = delta_value / delta_seconds`
- After the full session is known, normalize participation:
  - `bucket_volume_share = bucket_volume / total_day_volume`
- Fold each finalized bucket sample into Welford state so the profile can expose `mu`, `m2`, `variance`, and `sigma` without full reprocessing.

## Proposed seasonality record

Recommended shape in `trii-prod-historic-stats`:

```json
{
  "pk": "NUCO",
  "sk": "SEASONALITY_PROFILE",
  "symbol": "NUCO",
  "record_type": "seasonality_profile",
  "bucket_granularity_minutes": 30,
  "timezone": "America/Bogota",
  "total_days_processed": 128,
  "total_snapshots_processed": 15420,
  "last_source_captured_at": "2026-08-20T15:59:30-05:00",
  "last_updated_at": "2026-08-20T16:10:00-05:00",
  "weekly_profile": {
    "1": {
      "weekday_label": "monday",
      "days_processed": 24,
      "accumulated_day_volume": 4500000,
      "accumulated_day_value": 13500000000,
      "hours": {
        "09:00": {
          "accumulated_volume": 1200000,
          "accumulated_value": 3600000000,
          "bucket_vwap": 3000,
          "samples": 24,
          "volume_share_stats": {
            "sample_count": 24,
            "mu": 0.2667,
            "m2": 0.0141,
            "variance": 0.0006,
            "sigma": 0.0248
          },
          "vwap_stats": {
            "sample_count": 24,
            "mu": 3004.12,
            "m2": 18542.77,
            "variance": 805.34,
            "sigma": 28.39
          },
          "volume_rate_stats": {
            "sample_count": 24,
            "mu": 2500,
            "m2": 1400000,
            "variance": 60869.56,
            "sigma": 246.72
          },
          "value_rate_stats": {
            "sample_count": 24,
            "mu": 7500000,
            "m2": 580000000000,
            "variance": 25217391304.35,
            "sigma": 28.39
          }
        },
        "09:30": {
          "accumulated_volume": 900000,
          "accumulated_value": 2700000000,
          "bucket_vwap": 3000,
          "volume_share_stats": {
            "sample_count": 24,
            "mu": 0.2000,
            "m2": 0.0110,
            "variance": 0.0005,
            "sigma": 0.0219
          },
          "vwap_stats": {
            "sample_count": 24,
            "mu": 3002.45,
            "m2": 10921.55,
            "variance": 474.85,
            "sigma": 21.79
          },
          "volume_rate_stats": {
            "sample_count": 24,
            "mu": 1800,
            "m2": 920000,
            "variance": 40000,
            "sigma": 200
          },
          "value_rate_stats": {
            "sample_count": 24,
            "mu": 5400000,
            "m2": 420000000000,
            "variance": 18260869565.22,
            "sigma": 21.79
          }
        }
      }
    }
  }
}
```

Notes:

- Keep `pk = symbol` if this record will live in the existing `historic-stats` table. A prefixed partition key such as `TICKER#NUCO` would be a broader table-contract change.
- Keep the raw accumulators `accumulated_volume` and `accumulated_value` for fast reconstruction of aggregate participation and bucket VWAP.
- Also persist Welford state explicitly for the normalized signal that will be queried later. At minimum that should be `volume_share_stats` with `sample_count`, `mu`, `m2`, `variance`, and `sigma`.
- If the product will compare the current bucket price against its historical bucket price, persist a second Welford state for `vwap_stats`.
- The current implementation also persists `volume_rate_stats` and `value_rate_stats`, both normalized by the actual elapsed seconds between contiguous snapshots.
- `samples` should count finalized bucket observations, typically one per completed trading day per weekday-slot pair.
- `bucket_vwap` is a derived convenience field for the accumulated profile, not a substitute for `mean` and `stddev`.

## Infra implications for seasonality

This proposal requires more than adding one formula to `snapshot_metrics.py`.

Required changes:

- Add a new record contract to the `historic-stats` table documentation.
- Extend the updater and backfill lambdas with a **seasonality-specific aggregation path**.
- Load the previous contiguous snapshot per symbol to compute `delta_volume` and `delta_value`.
- Keep explicit session-boundary handling so market-open resets do not corrupt the profile.
- Decide whether the existing `gsi1` remains enough. If seasonality must be queried with another access pattern such as weekday-first or bucket-first, add a dedicated secondary index instead of overloading the current `symbol#metric` timeline index.
- Decide where intraday partial state lives before the day is finalized:
  - either inside the same `SEASONALITY_PROFILE` row with careful optimistic locking, or
  - in a separate scratch/state record that is consolidated at session close.
- Update any read path that currently assumes every row in `historic-stats` has the standard fields `metric`, `sample_count`, `mean`, `m2`, `stddev`, and `latest_value`.

## Recommended rollout for seasonality

1. Document the new `SEASONALITY_PROFILE` record type in the table contract before coding.
2. Add a seasonality-specific builder instead of forcing it through `build_stat_item`.
3. Backfill one symbol and one narrow date range in preview mode first.
4. Validate bucket totals against raw snapshots for a known day.
5. Validate `volume_share_stats.mu`, `m2`, `variance`, and `sigma` with an offline recomputation.
6. Only then enable the live incremental updater for seasonality writes.

## Event contract

The Lambda is manual and expects a JSON event.

Required:

- `metric_names`: list of metric keys to rebuild

Optional:

- `apply`: `false` by default; when `true`, the Lambda writes to `historic-stats`
- `symbols`: list of uppercase symbols; omit to scan all symbols
- `captured_at_from`: ISO-8601 timestamp with timezone
- `captured_at_to`: ISO-8601 timestamp with timezone

This contract currently supports only the standard metric keys declared in `snapshot_metrics.py`. A seasonality backfill will need either:

- a new supported key with dedicated branching logic, or
- a separate event field such as `record_types`.

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

## GitHub Actions invocation

There is also a manual workflow at `.github/workflows/historic-stats-backfill.yml`.

Use it when you want an operational backfill path without running AWS CLI locally.

Inputs:

- `apply_mode`: `preview` or `apply`
- `metric_name`: one supported metric from the choice list, or `custom`
- `custom_metric_name`: required only when `metric_name=custom`
- `symbols_csv`: optional comma-separated symbols such as `NUCO,ISA`
- `captured_at_from`: optional ISO-8601 timestamp with timezone
- `captured_at_to`: optional ISO-8601 timestamp with timezone

Workflow behavior:

- Builds the Lambda event payload for `trii-prod-historic-stats-backfill`
- Invokes the Lambda synchronously
- Publishes the payload and response in the GitHub Actions run summary
- Uploads `payload.json`, `response.json`, and `invoke-metadata.json` as artifacts

Current implementation note:

- `seasonality_profile` is now supported by the backfill Lambda with 30-minute intraday buckets in `America/Bogota`.
- `historic-stats-updater` still keeps only the live scalar metrics and has not yet been extended to maintain `seasonality_profile` in real time.

Operational note:

- The workflow uses the same GitHub OIDC role as Terraform. That role must be allowed to call `lambda:InvokeFunction` on `trii-prod-historic-stats-backfill`.

## Operational guidance

- Prefer backfilling **specific symbols** first when validating a new metric.
- Prefer backfilling **time windows** for large histories instead of one huge all-time run.
- Prefer backfilling **one metric per run** so the validation summary stays easy to audit.
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
