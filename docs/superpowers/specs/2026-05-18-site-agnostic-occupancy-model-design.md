# Site-Agnostic Occupancy Model — Design Spec

**Date:** 2026-05-18
**Author:** solo developer
**Status:** approved for implementation

---

## 1. Problem

After adding the full TfNSW facility list (44 Park&Ride lots) to the seed data, the
occupancy predictor returns a near-identical prediction for every newly-added car park.

### Root cause

The feature pipeline (`app/ml/features.py`) was extended to one-hot-encode **all 44**
TfNSW facilities (`park__<car_park_id>`), but only **two** of them — Gordon and
Lindfield — have real occupancy history. The other 42 facilities have 1–4 stray rows
each, all collected today by the live scheduler (`refresh_tfnsw`); `collect_history`
cannot backfill them because there are no per-facility history fixtures.

Consequences:

1. Training rows are effectively only Gordon + Lindfield. The chronological 7-day
   holdout pushes every new-facility row (all dated today) into the validation set,
   so the new facilities contribute **zero** rows to `train_df`.
2. 42 of the 44 `park__*` one-hot columns are constant-`0` during training. XGBoost
   never splits on them — they are inert dead features.
3. At inference, a new facility's lag features find no nearby history and fall back to
   the global `train_mean`; its one-hot is inert; temporal features depend only on the
   timestamp. The feature vector is therefore identical across all new facilities →
   identical prediction.

Verified empirically: holding lag inputs constant and varying only the facility
one-hot, `tfnsw_facility_8/16/25/39/490` all produce a byte-identical `0.96337`, while
Gordon (`0.96385`) and Lindfield (`0.96090`) differ.

This is a data/scope mismatch, not a model-code bug: the feature columns were extended
to all facilities, the training data was not.

## 2. Goal

Replace per-facility identity (one-hot) with a **site-agnostic** model: it predicts from
time, recent-occupancy (lag), and generic context features only. Adding a car park then
never changes the feature schema and never requires a retrain to be usable — the car
park works as soon as it has a little rolling history feeding the lags.

## 3. Decisions (resolved during brainstorming)

| Decision | Choice |
|---|---|
| Architecture | Site-agnostic model — drop `park__<id>` one-hots |
| Training & serving scope | All car parks (real TfNSW + simulated), served via ML |
| Context features | Venue type (commuter/retail) + capacity |
| Cold-start lag handling | Per-type mean imputation + `lag_imputed` indicator flag |

## 4. Feature schema

Fixed **12-column** schema. It does not grow when a car park is added.

| Feature | Definition |
|---|---|
| `hour_sin`, `hour_cos` | cyclical hour-of-day |
| `dow_sin`, `dow_cos` | cyclical day-of-week |
| `is_weekend` | 1.0 on Sat/Sun |
| `is_public_holiday` | 1.0 on NSW public holidays |
| `is_commuter` | 1.0 commuter venue / 0.0 retail venue |
| `log_capacity` | `log1p(total_spots)` |
| `lag_24h` | occupancy fraction 24h earlier (or per-type-mean imputation) |
| `lag_24h_imputed` | 1.0 when `lag_24h` was imputed, else 0.0 |
| `lag_168h` | occupancy fraction 168h earlier (or per-type-mean imputation) |
| `lag_168h_imputed` | 1.0 when `lag_168h` was imputed, else 0.0 |

`log_capacity` is continuous (not bucketed): XGBoost chooses its own split points, so an
arbitrary hand-cut bucket boundary would only discard information.

All `park__*` one-hot columns and the machinery that builds them are deleted:
`PARK_DUMMY_PREFIX`, `park_dummy_column_names`, `_park_dummies`,
`ml_training_car_park_ids`, and `predictor._facility_one_hot_ok`.

## 5. Venue type

Add a non-DB field to the `CarPark` model:

```python
venue_type: Literal["commuter", "retail"] = "commuter"
```

Same pattern as `total_spots` — populated from seed data, not stored in the `car_parks`
table, so no DB migration is needed.

Classification (from each simulated car park's `peak_hour` / `weekend_mult` profile):

- **retail**: `sim_westfield`, `sim_chatswood_chase`, `sim_mandarin_centre`,
  `sim_chatswood_west_cp`
- **commuter**: `sim_victoria_ave_cp`, `sim_artarmon_hampden`, `sim_st_leonards_plaza`,
  `sim_roseville_royal_st`, and **all TfNSW Park&Ride facilities**

The Chatswood seed list sets `venue_type` explicitly per car park; `_build_tfnsw_car_parks`
sets `venue_type="commuter"` for every TfNSW facility.

## 6. Training (`app/ml/train.py`)

- `_load_history` loads `occupancy_history` for **all** seeded car parks (not just
  `ml_training_car_park_ids`). New facilities' 1–4 stray rows are harmless: the
  site-agnostic model has no per-site parameters.
- `build_training_frame` attaches `is_commuter` and `log_capacity` per row from the seed
  car-park metadata, keyed by `car_park_id`.
- Missing lags within a car park's series are imputed with that car park's own mean
  (training has the real data) and the matching `lag_*_imputed` flag is set to 1.0.
- The bundle stores `type_mean_occupancy = {"commuter": float, "retail": float}` —
  the per-type mean occupancy over the training rows — for cold-start imputation at
  inference.
- `train_mean_occupancy` is retained for reporting only.
- `_min_training_rows` becomes a flat constant of `500` rows (the old `n * 8` formula
  was tied to the facility count and the one-hot scheme; with all car parks contributing
  history the realistic frame is several thousand rows).
- The chronological 7-day holdout split is unchanged — the simulated parks span
  Feb–May and split cleanly; new-facility rows landing in validation is harmless.

## 7. Inference (`app/ml/predictor.py`)

- `build_feature_row` gains the car park's `venue_type` and `total_spots` so it can emit
  `is_commuter` and `log_capacity`.
- `_lag_occupancy` returns `(value, imputed: bool)`. `imputed=True` when it falls through
  to the fallback; the fallback value is `type_mean_occupancy[venue_type]` from the
  bundle (not the global mean).
- The bundle-validity gate becomes a plain `bundle["feature_columns"] == FEATURE_COLUMNS`
  comparison; `_facility_one_hot_ok` and the `ml_training_car_park_ids` membership
  warning are deleted.
- `predict` looks up the car park's `venue_type` / `total_spots` from a
  `_CAR_PARK_BY_ID` map built from `ALL_CAR_PARKS`.

## 8. Serving (`app/services/prediction_service.py`)

- `predict_availability_tool` calls `predictor.predict` for **every** car park, not only
  `cp.source == "tfnsw"`.
- `_simulator_prediction` is used only as the fallback when no model bundle exists
  (`predictor.predict` returns `None`).
- The simulator remains the source of *current* occupancy for simulated car parks and
  the no-model fallback; only the *prediction* path moves to ML.

## 9. Files touched

| File | Change |
|---|---|
| `app/ml/features.py` | New 12-column schema; delete one-hot machinery; venue/capacity features; lag-imputed flags |
| `app/ml/predictor.py` | Site-agnostic feature row; per-type lag fallback; new bundle gate; delete `_facility_one_hot_ok` |
| `app/ml/train.py` | Load all history; per-type means in bundle; flat `_min_training_rows`; updated report |
| `app/data/seed_car_parks.py` | `venue_type` per car park |
| `app/models.py` | `CarPark.venue_type` field |
| `app/services/prediction_service.py` | ML path for all car parks; simulator as fallback only |
| `app/ml/collect_history.py` | Update stale docstring referencing "Gordon + Lindfield features" |
| `tests/test_ml_features.py` | New feature schema, venue/capacity, lag-imputed flags |
| `tests/test_ml_predictor.py` | Site-agnostic predictions; per-type cold-start fallback |
| `tests/test_prediction_service.py` | ML path for simulated car parks |
| `tests/test_collect_history.py` | Adjust if it references the one-hot id list |

After implementation, retrain → fresh `models/occupancy_v1.pkl` + `models/eval_report.md`.

## 10. Testing

Follow TDD — failing test first, then implementation.

- **features**: `FEATURE_COLUMNS` is exactly the 12 listed; `build_feature_row` emits
  `is_commuter`/`log_capacity` from car-park metadata; `build_training_frame` sets
  `lag_*_imputed` flags correctly on series gaps.
- **predictor**: two car parks of different `venue_type` with no lag history produce
  *different* predictions (the bug's regression test); a car park with real lag history
  uses it (`lag_imputed=0`).
- **prediction_service**: a simulated car park returns an ML result when a bundle
  exists, and the `_simulator_prediction` fallback when it does not.
- No network calls in tests; mock as per existing conventions.

## 11. Acceptance criteria

1. `FEATURE_COLUMNS` has 12 entries and contains no `park__*` column.
2. Adding a car park to the seed does not change `FEATURE_COLUMNS`.
3. For a fixed target datetime, two newly-added car parks of different venue type yield
   different predictions; same venue type with different lag history also differ.
4. All existing tests pass after updates; new regression test for the identical-prediction
   bug passes.
5. A freshly trained `occupancy_v1.pkl` loads and serves predictions for both a TfNSW and
   a simulated car park.

## 12. Out of scope

- Dropping facilities 1–5 ("Historical Only", never receive live data) from the seed —
  noted as future cleanup.
- Backfilling real TfNSW history for the new facilities.
- Any change to the LLM assistant, zone restrictions, or frontend.
