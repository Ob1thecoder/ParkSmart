# TfNSW History Data Audit

Collection run: `python -m app.ml.collect_history --days 120` on 2026-05-16.

| Facility | Rows | Distinct days | Earliest | Latest |
|---|---|---|---|---|
| tfnsw_gordon | 46,566 | 119 | 2026-01-16T11:02:18 | 2026-05-16T22:00:53 |
| tfnsw_lindfield | 33,914 | 121 | 2026-01-16T00:00:28 | 2026-05-16T21:58:04 |

## Gate criteria

Each facility must have ≥ 30 distinct days AND ≥ 500 rows.

- tfnsw_gordon: 119 days, 46,566 rows → PASS
- tfnsw_lindfield: 121 days, 33,914 rows → PASS

## Verdict

**GATE PASS.** Both facilities have ~4 months of history. Proceed with the full XGBoost pipeline (Tasks 3–6) and run real training in Task 4.

## Updated policy (2026-05-18)

`collect_history.py` inserts history for **all** seeded TfNSW IDs. Training (`python -m app.ml.train`) loads every such ID present in `occupancy_history`, building **one-hot `park__<car_park_id>` columns** alongside temporal + lag features. Per-facility audits like the table above can be repeated once additional sites accumulate rows; **`train.py`** separately enforces a **minimum pooled hourly training frame** (`_min_training_rows`) before fitting.
