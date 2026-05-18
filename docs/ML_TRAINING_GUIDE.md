# How a Training Dataset Works — The ParkSmart Occupancy Model

> **Revision 2026-05-18:** Module 10 documents inference-time lag widening, why many sites briefly looked “the same %”, **`simulator-v1` = flat 50%** without a bundled model — **plus Module 8 § “Why the number often looks too high”** (confidence heuristic vs calibrated probability). A walkthrough using the code you just built. I'll assume you can read Python but have never trained a model. We'll go from raw API data to a trained predictor, stopping to explain *why* at every step.

---

## Module 0 — The One Idea Behind All Supervised ML

A model is a function that maps inputs to an output:

```
prediction = f(inputs)
```

You don't write `f` by hand. You show the computer thousands of examples of `inputs → correct output`, and an algorithm figures out an `f` that fits them. That's **"training."**

### Key Vocabulary

| Term | Definition |
|------|------------|
| **Features (X)** | The inputs. *"It's 6pm, Friday, at Gordon, and it was 80% full at this hour last week."* |
| **Target (y)** | The answer you want predicted. *"It was 85% full."* |

The training dataset is just a big table: each row is one example, the feature columns are **X**, and one special column is **y**. Everything in this lecture is about how we turn messy real-world data into that clean table.

---

## Module 1 — The Raw Material

Your `collect_history.py` pulled **80,467 rows** from the TfNSW API into the `occupancy_history` table. One raw record looks like this:

```json
{
  "spots": "213",
  "occupancy": { "total": "27" },
  "MessageDate": "2026-05-10T06:00:00",
  "facility_id": "6"
}
```

Stored in SQLite as:

| car_park_id | ts | available | total_spots |
|-------------|-----|-----------|-------------|
| tfnsw_gordon | 2026-05-10T06:00:00 | 186 | 213 |

### Why This Isn't a Training Dataset Yet

This is **raw observations**. A model cannot learn from this directly, for three reasons:

1. **No target column** — "occupancy %" doesn't exist, it's implied
2. **Columns aren't model-readable** — a model eats numbers, and `"2026-05-10T06:00:00"` is a string
3. **Columns don't carry predictive signal** — a raw timestamp doesn't tell the model "this is rush hour"

The job of `features.py::build_training_frame` is to fix all three.

---

## Module 2 — Step 1: Manufacture the Target

The model should predict how full a car park is — a number from **0** (empty) to **1** (full). The raw data only has `available` and `total_spots`, so we compute it:

```python
df["occ"] = 1.0 - df["available"] / df["total_spots"]
```

### Worked Example: Gordon Across One Real Day

| Time | Available | Total | occ = 1 − avail/total | Meaning |
|------|-----------|-------|----------------------|---------|
| 06:00 | 186 | 213 | **0.127** | 13% full — almost empty |
| 09:00 | 15 | 213 | **0.930** | 93% full — commuters arrived |
| 17:00 | 68 | 213 | **0.681** | 68% full — some have left |

That `occ` column is now our **target y**. The whole point of the model is: given the context of a moment, predict this number.

> ⚠️ **Data Quality Note**: TfNSW sometimes reports `occupied > spots` (sensor noise, maintenance vehicles). This makes `occ` go slightly negative or above 1. Your model's `max_residual` of 1.55 is a fingerprint of exactly this — a few dirty rows. The fix is one line: `df["occ"].clip(0, 1)`.

---

## Module 3 — Step 2: Collapse to One Row Per Hour

Real sensors report irregularly — sometimes every few minutes, sometimes with gaps. But we want to predict at **hourly resolution**. So we bucket every reading into its hour and average:

```python
df["hour"] = df["ts"].dt.floor("h")          # 06:47 and 06:12 both become 06:00
hourly = df.groupby(["car_park_id", "hour"])["occ"].mean()
```

- `floor("h")` chops the minutes off
- `groupby(...).mean()` says: for each (car park, hour) pair, average all the readings inside it

After this, every example is exactly **one car park at one specific hour**. This is the *grain* of your dataset — the thing one row represents.

---

## Module 4 — Step 3: Feature Engineering (The Heart of It)

Now we build the input columns. This is where beginners underestimate the work: **a model is only as smart as the features you hand it**. XGBoost can't "see" a timestamp the way you do. You have to translate human intuition (*"Friday evening near a station is busy"*) into numbers.

Your `FEATURE_COLUMNS` lists **every numeric input**: **8 temporal + lag floats** (`hour_sin` … `lag_168h`) plus **one `park__…` dummy per seeded TfNSW site** (~44 binary columns today). Conceptually we'll walk the *types*, not memorise sixty column names.

### 4a. Cyclical Time — `hour_sin`, `hour_cos`, `dow_sin`, `dow_cos`

**The trap**: Just feed the hour as 0–23. To the model, hour 23 and hour 0 would look 23 apart — maximally different — when in reality they're adjacent (11pm and midnight). The model would never learn that "late night" is one continuous period.

**The fix**: Place the hour on a circle. Any angle has a sine and a cosine, and the circle wraps around naturally — 23:00 and 00:00 land right next to each other.

```python
def _cyclical(value, period):
    angle = 2.0 * np.pi * value / period
    return np.sin(angle), np.cos(angle)
```

**Example calculations:**

| Hour | Angle | hour_sin | hour_cos |
|------|-------|----------|----------|
| 6 (6am) | 90° | 1.0 | 0.0 |
| 18 (6pm) | 270° | -1.0 | 0.0 |

The model now sees morning and evening as genuinely opposite points, and midnight ≈ 1am. Same trick for day-of-week (period = 7).

> 💡 **Why two columns (sin AND cos)?** One alone is ambiguous — `sin = 1.0` happens at one angle, but `sin = 0.5` happens at two different hours. You need the pair to pin down a unique point on the circle.

### 4b. Facility identity — **`park__<car_park_id>`** columns (multi–one-hot)

**The trap:** feeding a single categorical integer (Gordon=`0`, Lindfield=`1`, …)
implies a bogus ordering unless you deliberately choose an ordinal encoding.

**The implementation:** Allocate one binary column per seeded TfNSW facility
(`FEATURE_COLUMNS` in `features.py`; names like `park__tfnsw_gordon`,
`park__tfnsw_facility_25`, … — **exactly one** column is hot per row).

| Car park id | … | park__tfnsw_gordon | … | park__tfnsw_lindfield | … |
|-------------|---|---------------------|---|-------------------------|---|
| `tfnsw_gordon` | … | **1.0** | … | 0.0 | … |

This lets one **shared XGBoost regressor** ingest calendar + lag features common to all sites while still allocating capacity to learn distinct utilisation curves. When a TfNSW car park lacks history, pooled patterns still help once enough cross-site samples exist — but per-site residuals may stay high until that site collects data.

### 4c. Boolean Flags — `is_weekend`, `is_public_holiday`

Some signal is simplest as a yes/no:

```python
"is_weekend": 1.0 if dt.weekday() >= 5 else 0.0,
"is_public_holiday": 1.0 if dt.date() in _NSW_HOLIDAYS else 0.0,
```

A commuter car park is dead on weekends and holidays. Without `is_public_holiday`, the model would see a Tuesday that behaves like a Sunday and be badly wrong. We pull NSW holiday dates from the `holidays` package so we don't hand-maintain a list.

### 4d. Lag Features — `lag_24h`, `lag_168h` ⭐

> **This is the single biggest lever in time-series prediction: the best clue about the future is the recent past.**

| Feature | Description | Why It Matters |
|---------|-------------|----------------|
| `lag_24h` | How full was this car park at this same hour **yesterday**? | Captures daily cycle (empty at night, full at 9am) |
| `lag_168h` | How full was it at this same hour **exactly one week ago**? (168 = 24 × 7) | Captures weekly cycle (Mondays ≠ Saturdays). 6pm last Friday is a fantastic predictor of 6pm this Friday. |

This property — a value being correlated with its own past — is called **autocorrelation**, and exploiting it is most of what makes time-series models work.

**Building the lags in `build_training_frame`:**

```python
occ_by_hour = dict(zip(grp["hour"], grp["occ"]))   # {hour: occupancy} lookup
cp_mean = grp["occ"].mean()                         # this car park's average

for hour, occ in occ_by_hour.items():
    lag_24h  = occ_by_hour.get(hour - pd.Timedelta(hours=24),  cp_mean)
    lag_168h = occ_by_hour.get(hour - pd.Timedelta(hours=168), cp_mean)
```

For each hour we look backwards into the same dictionary. The `.get(key, cp_mean)` is the fallback: if 24h ago is missing (a sensor gap, or the very first day of data), we substitute the car park's overall average rather than crash or leave a hole.

---

## Module 5 — The Finished Training Table

After all that, `build_training_frame` returns a clean table. One example row:

| hour_sin | hour_cos | dow_sin | dow_cos | … | `park__tfnsw_*` columns (one-hot) … | lag_24h | lag_168h | **target** |
|----------|----------|---------|---------|---|----------------------------------------|---------|----------|------------|
| -1.0 | 0.0 | 0.43 | -0.90 | … | Exactly one **`1.0`** (here: Gordon), rest `0` | 0.88 | 0.91 | **0.86** |

**Read it as a sentence:**

> "At 6pm (hour_sin/cos), on a Friday (dow_sin/cos), not a weekend or holiday, at **whatever site that one-hot selects**, where it was 88% full yesterday at 6pm and 91% full last Friday at 6pm — it turned out to be **86% full**."

That last column, `target`, is the answer. Everything to its left — apart from bookkeeping columns like timestamps — are **X**. Thousands of pooled rows spanning every TfNSW facility are ideal; the bundled XGBoost model learns correlations shared across commuter sites while letting the `park__…` split carve out facility-specific biases.

---

## Module 6 — Splitting the Data: Train vs. Validation

Before training you must **hold back some data to grade yourself**. If you train on 100% of the data and test on the same data, of course it looks great — it memorized the answers. That tells you nothing about new predictions.

### The Wrong Way (Data Leakage)

The instinct is to shuffle randomly and hold out 20%. For time series, this is a serious bug called **data leakage**: random shuffling lets the model train on June while being tested on May — it would "learn" the future to predict the past, which it can never do in production.

### The Correct Way (Chronological Split)

```python
cutoff   = frame["ts"].max() - pd.Timedelta(days=holdout_days)  # 7 days
train_df = frame[frame["ts"] <= cutoff]   # everything older  → learn from
val_df   = frame[frame["ts"] >  cutoff]   # last 7 days       → graded on
```

This honestly simulates production: train on the past, predict the genuinely-unseen future.

**Your run:** 5,024 training rows / 286 validation rows.

---

## Module 7 — What "Training" Actually Does (XGBoost)

```python
occ_model = XGBRegressor(n_estimators=200, max_depth=4, learning_rate=0.05, ...)
occ_model.fit(X_train, y_train)
```

That `.fit()` call is the training. XGBoost is **gradient-boosted decision trees**. Unpacked:

| Concept | Explanation |
|---------|-------------|
| **Decision tree** | A flowchart of yes/no questions: *"is_gordon = 1? → is hour_sin < 0? → predict 0.7."* One shallow tree (`max_depth=4` = at most 4 questions deep) is weak — it captures a rough trend and misses nuance. |
| **Boosting** | Build trees in sequence, each one trained to fix the leftover errors of all the trees before it. Tree 1 makes a crude guess. Tree 2 doesn't re-predict occupancy — it predicts *"how wrong was tree 1?"* and corrects it. Tree 3 corrects what's still wrong. Repeat 200 times (`n_estimators=200`). |
| **Learning rate** | `learning_rate=0.05` means each tree's correction is only partly applied — small, cautious steps. Slower, but it avoids overshooting and overfitting. |

The final model is the **sum of all 200 trees**. Together they approximate the function mapping the **calendar + lag + facility** vector → occupancy fraction, far better than any single shallow tree would. Nothing is "programmed" — the split questions/thresholds are learned from whichever hourly rows landed in `build_training_frame` after TfNSW collection.
---

## Module 8 — The Second Model: Predicting Confidence

Your pipeline trains **two models**:
1. The first predicts occupancy
2. The second predicts *how wrong the first one tends to be*

```python
abs_resid   = np.abs(y_train - occ_model.predict(X_train))   # the error on each row
resid_model = XGBRegressor(**params)
resid_model.fit(X_train, abs_resid)                          # learn WHERE errors are big
```

A **residual** is just `actual − predicted` — the miss. We take its absolute value (size of the miss, ignoring direction) and train a whole second XGBoost to predict that.

### Why Do This?

Because errors aren't uniform. The model is rock-solid at 3am (always empty, easy) and shaky during a chaotic Friday peak. The residual model learns those patterns, so at prediction time we can say:

- *"87% full, **high confidence**"* vs.
- *"87% full, **low confidence**"*

**Confidence calculation at inference** (`predictor.py`):

```python
resid = float(bundle["residual_model"].predict(X)[0])   # predicted typical |error| for rows like this
max_resid = bundle["max_residual"] or 1.0              # max(|y_train - occ_model.predict|), from training
confidence = 1.0 - min(max(resid / max_resid, 0.0), 1.0)
```

So **confidence = 1 − (predicted absolute error / worst-case training error)**, clamped to **[0, 1]**.

- **Large** predicted residual (this situation is like the messy parts of training) → ratio → **1**, confidence **low**.
- **Small** predicted residual → ratio ≈ **0**, confidence **near 1**.

### Why the number often looks “too high” (e.g. 0.9+) — read this carefully

**This is not a calibrated probability.** It does **not** mean “there is a 93% chance the lot is within X% of this forecast.” It is a **heuristic** tied to training error and a **generous normalizer**.

| Mechanism | Effect |
|-----------|--------|
| **`max_residual` is the *maximum* absolute error on training rows** | A few bad rows (sensor glitches, impossible occupancy vs capacity, etc.) push `max_residual` up — **your `eval_report.md` might show ~1.5+ on a 0–1 occupancy scale**. Everything is divided by that large number. |
| **Typical predicted residuals are moderate** | For “ordinary” feature vectors the second model often predicts something like **0.08–0.15** on the occupancy-fraction scale — small **compared to** a 1.5 max, so **1 − 0.1/1.5 ≈ 0.93** — hence **very high displayed confidence** even when MAE on holdout is only “good,” not “oracle.” |
| **Residual model trains on the same `X_train` where fit is already OK** | It learns patterns of *remaining* error after boosting; for many rows that error is **shrunk**, so predicted residuals stay **below** the extreme tail that set `max_residual`. |
| **No holdout calibration** | We don’t map this score to measured coverage (e.g. “90% of the time the error is below 0.05 on the occupancy scale”). The UI label “High / Medium / Low” (e.g. thresholds around 0.8 / 0.5) is **relative**, not a statistical guarantee. |

**How to interpret it for users:** Treat it as **“model self-consistency vs. the worst errors it saw in training”**, not **“trust this percentage point-for-point.”** The **holdout MAE** (Module 9) is closer to an **honest accuracy** statement for typical hours.

**If you want softer or more honest-feeling scores later (not implemented by default):** clip dirty `occ` before fitting, use a **percentile** (e.g. p95) of `|residual|` instead of **`max`**, scale by **validation MAE**, or rename the product string to **“certainty (heuristic)”** so it isn’t read as a literal confidence interval.

> 📝 Dirty training rows **inflate `max_residual`** and **implicitly inflate confidence** for normal cases. Cleaning/clipping the target (Module 2) helps both MAE and this scale.

---

## Module 9 — Grading: What MAE 0.031 Means

```python
val_pred = occ_model.predict(val_df[FEATURE_COLUMNS])   # predict the held-out week
val_mae  = np.abs(val_df["target"] - val_pred).mean()   # average miss
```

**MAE = Mean Absolute Error** — predict every hour of the held-out week, measure each miss, average them.

### Your Result: 0.031

Occupancy is a 0–1 scale, so **0.031 = 3.1 percentage points**.

On a week the model had never seen, its fullness estimate was off by ~3pp on average:
- Predict 80% → reality is roughly **77–83%**

For parking guidance, that's genuinely good. And because it's measured on held-out future data, it's an **honest number**, not a memorization mirage.

---

## Module 10 — Under the Hood at Prediction Time (Lags & “Flat” Forecasts)

**At training time**, `lag_24h` / `lag_168h` come from **`build_training_frame`**: keyed off real `(car_park_id, hour)` rows in `occupancy_history`.

**At prediction time** you're asking about the future — *"how full will Hornsby be next Tuesday 6pm?"* The clock times **24h / 168h before** your target mostly **have not occurred yet**. So **`predictor.py`** looks up **historic** occupancy around those anchors:

```python
lag_24h  = _lag_occupancy(db_path, car_park_id, target_dt - timedelta(hours=24),  mean)
lag_168h = _lag_occupancy(db_path, car_park_id, target_dt - timedelta(hours=168), mean)
```

`_lag_occupancy` (**per facility**, not pooled) resolves in tiers:

1. **±90 min** of nominal — nearest row (matches tight sensor-ish sampling where it exists).
2. If empty: **±72 h** around nominal — nearest row (**stops sparse sites from collapsing to one global fallback** — see caution below).
3. If still empty: **most recent snapshot on or before nominal**, up to **180 days** back.
4. Only then: the bundle’s **`train_mean_occupancy`** (training-set global mean).

Older behaviour used only ±90 min then jumped straight to the **same global mean for both** lags whenever a facility had gaps. Combined with hourly features, tens of commuter sites landed on **almost the same predicted %** despite different `park__…` one-hots. **Version note (2026-05):** widened tiers + facility-specific stale prior fix that pathology.

### Production gotcha — `simulator-v1` on TfNSW

If **`occupancy_v1.pkl` is absent** from the runtime, TfNSW falls back to **`prediction_service`**’s stub: **`capacity // 2` → exactly 50% full for every TfNSW car park.** The map then looks “broken” — all Park&Rides at the **same rounded percentage.** Fix: bundle the artefact (`models/occupancy_v1.pkl`) into the Docker image or copy it beside the DB; confirm responses show **`model_version: "xgboost-v1"`**.

### API lookup gotcha — pass stable IDs from the SPA

`/api/predict?location=` is resolved through **`find_car_park`** (exact id/name, then fuzzy). Very loose fuzzy match could map junk text to Gordon. **Prefer `OccupancyResponse.car_park_id`** as **`location`** (e.g. `tfnsw_facility_25`) from the parity batch of predict calls.**Version note:** the React hook fans out with **`car_park_id`**, not display name (`Park&Ride` strings with **`&`** are uglier via query params).

### Why still no `lag_1h`?

For a horizon days ahead, “one hour before the target instant” often **hasn’t happened**; “same-ish time last week” is usually in-history and supports **`lag_168h`**.

The feature vector at inference matches the **`feature_columns`** list inside **`occupancy_v1.pkl`**; both XGBoost heads consume that layout; output carries **`model_version: "xgboost-v1"`** when ML runs.

---

## The Whole Pipeline in One Breath

```
TfNSW API
  ↓
collect_history.py     → raw rows → occupancy_history table
  ↓
build_training_frame   → target (1−avail/total), hourly buckets,
                         cyclical time, weekend/holiday flags, `park__…` dummies, lags
  ↓
chronological split    → older = train (5024) · last 7 days = validation (286)
  ↓
XGBoost .fit()         → 200 trees, each fixing the last one's errors
  ↓
second XGBoost         → learns the error pattern → confidence
  ↓
MAE on validation      → 0.031 — honest 3pp accuracy on unseen data
  ↓
pickle bundle          → models/occupancy_v1.pkl
  ↓
predictor.py           → per-site lag lookup (±90m → ±72h → recent history) → predict
```

---

## The Takeaway

> **~80% of the work and ~80% of the accuracy lives in Modules 2–5 — turning raw data into honest, well-engineered features.**

The `.fit()` call is one line. Beginners obsess over the algorithm; **engineers obsess over the dataset**.

---

## Going Deeper

Want to explore more? Consider:
- Module 10 — inference lags · Module 8 — **confidence is heuristic, often high numerically**.
- A hand-traced single decision tree
- The math of cyclical encoding
- How to clean that `max_residual` bug and retrain
