Lecture: How a Training Dataset Works — The ParkSmart Occupancy Model

  A walkthrough using the code you just built. I'll assume you can read Python but have never trained a model.
  We'll go from raw API data to a trained predictor, stopping to explain why at every step.

  ---
  Module 0 — The one idea behind all supervised ML
  
  A model is a function that maps inputs to an output:

  prediction = f(inputs)

  You don't write f by hand. You show the computer thousands of examples of inputs → correct output, and an
  algorithm figures out an f that fits them. That's "training."

  Two vocabulary words you'll see everywhere:

  - Features (X) — the inputs. "It's 6pm, Friday, at Gordon, and it was 80% full at this hour last week."
  - Target (y) — the answer you want predicted. "It was 85% full."

  The training dataset is just a big table: each row is one example, the feature columns are X, and one special
  column is y. Everything in this lecture is about how we turn messy real-world data into that clean table.

  ---
  Module 1 — The raw material
  
  Your collect_history.py pulled 80,467 rows from the TfNSW API into the occupancy_history table. One raw record
  looks like this:

  { "spots": "213", "occupancy": { "total": "27" }, "MessageDate": "2026-05-10T06:00:00", "facility_id": "6" }

  Stored in SQLite as:

  ┌──────────────┬─────────────────────┬───────────┬─────────────┐
  │ car_park_id  │         ts          │ available │ total_spots │
  ├──────────────┼─────────────────────┼───────────┼─────────────┤
  │ tfnsw_gordon │ 2026-05-10T06:00:00 │ 186       │ 213         │
  └──────────────┴─────────────────────┴───────────┴─────────────┘

  This is not a training dataset yet. It's raw observations. A model cannot learn from this directly, for three
  reasons we'll fix one at a time:

  1. There's no target column — "occupancy %" doesn't exist, it's implied.
  2. The columns aren't model-readable — a model eats numbers, and "2026-05-10T06:00:00" is a string.
  3. The columns don't yet carry predictive signal — a raw timestamp doesn't tell the model "this is rush hour."

  The job of features.py::build_training_frame is to fix all three.

  ---
  Module 2 — Step 1: Manufacture the target

  The model should predict how full a car park is — a number from 0 (empty) to 1 (full). The raw data only has
  available and total_spots, so we compute it:

  df["occ"] = 1.0 - df["available"] / df["total_spots"]

  Worked example, Gordon across one real day:

  ┌───────┬───────────┬───────┬───────────────────────┬──────────────────────────────┐
  │ Time  │ available │ total │ occ = 1 − avail/total │           Meaning            │
  ├───────┼───────────┼───────┼───────────────────────┼──────────────────────────────┤
  │ 06:00 │ 186       │ 213   │ 0.127                 │ 13% full — almost empty      │
  ├───────┼───────────┼───────┼───────────────────────┼──────────────────────────────┤
  │ 09:00 │ 15        │ 213   │ 0.930                 │ 93% full — commuters arrived │
  ├───────┼───────────┼───────┼───────────────────────┼──────────────────────────────┤
  │ 17:00 │ 68        │ 213   │ 0.681                 │ 68% full — some have left    │
  └───────┴───────────┴───────┴───────────────────────┴──────────────────────────────┘

  That occ column is now our target y. The whole point of the model is: given the context of a moment, predict
  this number.

  ▎ Under the hood gotcha: TfNSW sometimes reports occupied > spots (sensor noise, maintenance vehicles). That 
  ▎ makes occ go slightly negative or above 1. Your model's max_residual of 1.55 is a fingerprint of exactly this 
  ▎ — a few dirty rows. The fix is one line — df["occ"].clip(0, 1) — and it's the data-quality note I flagged 
  ▎ earlier.

  ---
  Module 3 — Step 2: Collapse to one row per hour
  
  Real sensors report irregularly — sometimes every few minutes, sometimes with gaps. But we want to predict at 
  hourly resolution. So we bucket every reading into its hour and average:

  df["hour"] = df["ts"].dt.floor("h")          # 06:47 and 06:12 both become 06:00
  hourly = df.groupby(["car_park_id", "hour"])["occ"].mean()

  floor("h") chops the minutes off. groupby(...).mean() says: for each (car park, hour) pair, average all the 
  readings inside it. After this, every example is exactly one car park at one specific hour. This is the grain of
   your dataset — the thing one row represents.

  ---
  Module 4 — Step 3: Feature engineering (the heart of it)
  
  Now we build the input columns. This is where beginners underestimate the work: a model is only as smart as the 
  features you hand it. XGBoost can't "see" a timestamp the way you do. You have to translate human intuition
  ("Friday evening near a station is busy") into numbers.

  Your FEATURE_COLUMNS has 10. Let's go through each type.

  4a. Cyclical time — hour_sin, hour_cos, dow_sin, dow_cos

  Naïve approach: just feed the hour as 0–23. This is a trap. To the model, hour 23 and hour 0 would look 23 apart
   — maximally different — when in reality they're adjacent (11pm and midnight). The model would never learn that
  "late night" is one continuous period.

  The fix: place the hour on a circle. Any angle has a sine and a cosine, and the circle wraps around naturally —
  23:00 and 00:00 land right next to each other.

  def _cyclical(value, period):
      angle = 2.0 * np.pi * value / period
      return np.sin(angle), np.cos(angle)

  For hour = 6, period = 24: angle = 2π·6/24 = 90°, so hour_sin = 1.0, hour_cos = 0.0. For hour = 18: angle =
  270°, hour_sin = -1.0. The model now sees morning and evening as genuinely opposite points, and midnight ≈ 1am.
  Same trick for day-of-week (period = 7).

  ▎ Why two columns (sin AND cos)? One alone is ambiguous — sin = 1.0 happens at one angle, but sin = 0.5 happens 
  ▎ at two different hours. You need the pair to pin down a unique point on the circle.

  4b. Categorical — is_gordon, is_lindfield (one-hot encoding)

  The car park is a category, not a number. You might think "set Gordon = 0, Lindfield = 1." Trap again — that
  tells the model Lindfield is "greater than" Gordon, and that the gap between them is exactly 1. That ordering is
   fiction.

  One-hot encoding gives each category its own 0/1 column:

  ┌───────────┬───────────┬──────────────┐
  │ car park  │ is_gordon │ is_lindfield │
  ├───────────┼───────────┼──────────────┤
  │ Gordon    │ 1.0       │ 0.0          │
  ├───────────┼───────────┼──────────────┤
  │ Lindfield │ 0.0       │ 1.0          │
  └───────────┴───────────┴──────────────┘

  No fake ordering. The model can learn a separate behavior for each car park (Gordon has 213 spots and a heavier
  commuter peak; Lindfield has 94).

  4c. Boolean flags — is_weekend, is_public_holiday

  Some signal is simplest as a yes/no:

  "is_weekend": 1.0 if dt.weekday() >= 5 else 0.0,
  "is_public_holiday": 1.0 if dt.date() in _NSW_HOLIDAYS else 0.0,

  A commuter car park is dead on weekends and holidays. Without is_public_holiday, the model would see a Tuesday
  that behaves like a Sunday and be badly wrong. We pull NSW holiday dates from the holidays package so we don't
  hand-maintain a list.

  4d. Lag features — lag_24h, lag_168h (the most important idea in this lecture)

  Here's the single biggest lever in time-series prediction: the best clue about the future is the recent past.

  - lag_24h — how full was this car park at this same hour yesterday?
  - lag_168h — how full was it at this same hour exactly one week ago? (168 = 24 × 7)

  Why these two specifically? Parking has two strong rhythms:
  - A daily cycle (empty at night, full at 9am) → captured by lag_24h.
  - A weekly cycle (Mondays ≠ Saturdays) → captured by lag_168h. 6pm last Friday is a fantastic predictor of 6pm
  this Friday.
  
  This property — a value being correlated with its own past — is called autocorrelation, and exploiting it is
  most of what makes time-series models work.

  Building the lags in build_training_frame:

  occ_by_hour = dict(zip(grp["hour"], grp["occ"]))   # {hour: occupancy} lookup
  cp_mean = grp["occ"].mean()                         # this car park's average

  for hour, occ in occ_by_hour.items():
      lag_24h  = occ_by_hour.get(hour - pd.Timedelta(hours=24),  cp_mean)
      lag_168h = occ_by_hour.get(hour - pd.Timedelta(hours=168), cp_mean)

  For each hour we look backwards into the same dictionary. The .get(key, cp_mean) is the fallback: if 24h ago is
  missing (a sensor gap, or the very first day of data), we substitute the car park's overall average rather than
  crash or leave a hole.

  ---
  Module 5 — The finished training table

  After all that, build_training_frame returns a clean table. One real-ish row:

  ┌────────┬────────┬───────┬───────┬──────────┬──────────┬─────────┬───────────┬───────┬────────┬──────┐
  │ hour_s │ hour_c │ dow_s │ dow_c │ is_weeke │ is_holid │ is_gord │ is_lindfi │ lag_2 │ lag_16 │ targ │
  │   in   │   os   │  in   │  os   │    nd    │    ay    │   on    │    eld    │  4h   │   8h   │  et  │
  ├────────┼────────┼───────┼───────┼──────────┼──────────┼─────────┼───────────┼───────┼────────┼──────┤
  │ -1.0   │ 0.0    │ 0.43  │ -0.90 │ 0        │ 0        │ 1       │ 0         │ 0.88  │ 0.91   │ 0.86 │
  └────────┴────────┴───────┴───────┴──────────┴──────────┴─────────┴───────────┴───────┴────────┴──────┘

  Read it as a sentence: "At 6pm (hour_sin/cos), on a Friday (dow_sin/cos), not a weekend or holiday, at Gordon, 
  where it was 88% full yesterday at 6pm and 91% full last Friday at 6pm — it turned out to be 86% full."

  That last column, target, is the answer. The other 10 are X. 5,310 rows like this is your training dataset. The
  model's job: learn the pattern connecting the 10 numbers to the answer, well enough to fill in the answer for an
   hour it has never seen.

  ---
  Module 6 — Splitting the data: train vs. validation
  
  Before training you must hold back some data to grade yourself. If you train on 100% of the data and test on the
   same data, of course it looks great — it memorized the answers. That tells you nothing about new predictions.

  The instinct is to shuffle randomly and hold out 20%. For time series, that is a serious bug called data 
  leakage: random shuffling lets the model train on June while being tested on May — it would "learn" the future
  to predict the past, which it can never do in production.

  The correct split is chronological — hold out the most recent slice:

  cutoff   = frame["ts"].max() - pd.Timedelta(days=holdout_days)  # 7 days
  train_df = frame[frame["ts"] <= cutoff]   # everything older  → learn from
  val_df   = frame[frame["ts"] >  cutoff]   # last 7 days       → graded on

  This honestly simulates production: train on the past, predict the genuinely-unseen future. Your run gave 5,024 
  training rows / 286 validation rows.

  ---
  Module 7 — What "training" actually does (XGBoost)

  occ_model = XGBRegressor(n_estimators=200, max_depth=4, learning_rate=0.05, ...)
  occ_model.fit(X_train, y_train)

  That .fit() call is the training. XGBoost is gradient-boosted decision trees. Unpacked:

  - A decision tree is a flowchart of yes/no questions: "is_gordon = 1? → is hour_sin < 0? → predict 0.7." One
  shallow tree (max_depth=4 = at most 4 questions deep) is weak — it captures a rough trend and misses nuance.
  - Boosting = build trees in sequence, each one trained to fix the leftover errors of all the trees before it.
  Tree 1 makes a crude guess. Tree 2 doesn't re-predict occupancy — it predicts "how wrong was tree 1?" and
  corrects it. Tree 3 corrects what's still wrong. Repeat 200 times (n_estimators=200).
  - learning_rate=0.05 means each tree's correction is only partly applied — small, cautious steps. Slower, but it
   avoids overshooting and overfitting.

  The final model is the sum of all 200 trees. Together they approximate the function f(10 features) → occupancy
  far better than any single tree. Nothing is "programmed" — the tree questions and thresholds are all discovered
  from your 5,024 rows.

  ---
  Module 8 — The second model: predicting confidence

  Your pipeline trains two models. The first predicts occupancy. The second predicts how wrong the first one tends
   to be.

  abs_resid   = np.abs(y_train - occ_model.predict(X_train))   # the error on each row
  resid_model = XGBRegressor(**params)
  resid_model.fit(X_train, abs_resid)                          # learn WHERE errors are big

  A residual is just actual − predicted — the miss. We take its absolute value (size of the miss, ignoring
  direction) and train a whole second XGBoost to predict that.

  Why? Because errors aren't uniform. The model is rock-solid at 3am (always empty, easy) and shaky during a
  chaotic Friday peak. The residual model learns those patterns, so at prediction time we can say "87% full, high 
  confidence" vs. "87% full, low confidence." Confidence is computed by scaling the predicted error against the
  worst error seen:

  confidence = 1.0 - clip(predicted_residual / max_residual, 0, 1)

  Big expected error → low confidence. Small → high confidence. (And max_residual = 1.55 from the dirty rows is
  why this scaling is a bit loose — clean the target and it tightens.)

  ---
  Module 9 — Grading: what MAE 0.031 means

  val_pred = occ_model.predict(val_df[FEATURE_COLUMNS])   # predict the held-out week
  val_mae  = np.abs(val_df["target"] - val_pred).mean()   # average miss

  MAE = Mean Absolute Error — predict every hour of the held-out week, measure each miss, average them. You got
  0.031.

  Occupancy is a 0–1 scale, so 0.031 = 3.1 percentage points. On a week the model had never seen, its fullness
  estimate was off by ~3pp on average — predict 80%, reality is roughly 77–83%. For parking guidance, that's
  genuinely good. And because it's measured on held-out future data, it's an honest number, not a memorization
  mirage.

  ---
  Module 10 — Under the hood at prediction time (the lag trap)
  
  One last subtlety that trips up beginners. At training time, lag_24h was easy — yesterday already happened, the
  value was sitting in the table.

  At prediction time you're asking about the future — "how full will Gordon be next Tuesday 6pm?" There is no row
  for "24h before next Tuesday 6pm" because that hasn't happened either. So predictor.py goes and fetches the lags
   from history:

  lag_24h  = _lag_occupancy(db_path, car_park_id, target_dt - timedelta(hours=24),  mean)
  lag_168h = _lag_occupancy(db_path, car_park_id, target_dt - timedelta(hours=168), mean)

  _lag_occupancy queries occupancy_history for the nearest reading within ±90 minutes of that earlier moment. If
  nothing is there, it falls back to the training mean (stored in the model bundle). This is also why lag_1h was 
  dropped from the design — for a prediction 5 days out, "1 hour before" is still in the future and genuinely
  unknowable, but "same hour last week" is comfortably in the past.

  The 10 fetched/computed features go into a one-row DataFrame, both models run, and you get back the prediction
  dict with model_version: "xgboost-v1".

  ---
  The whole pipeline in one breath

  TfNSW API
    → collect_history.py     raw rows  → occupancy_history table
    → build_training_frame   target (1−avail/total), hourly buckets,
                             cyclical time, one-hot, holiday flags, lags
    → chronological split    older = train (5024) · last 7 days = validation (286)
    → XGBoost .fit()         200 trees, each fixing the last one's errors
    → second XGBoost         learns the error pattern → confidence
    → MAE on validation      0.031 — honest 3pp accuracy on unseen data
    → pickle bundle          models/occupancy_v1.pkl
    → predictor.py           fetch lags from history → predict the future

  The lesson to take with you: ~80% of the work and ~80% of the accuracy lives in Modules 2–5 — turning raw data
  into honest, well-engineered features. The .fit() call is one line. Beginners obsess over the algorithm;
  engineers obsess over the dataset.

  ---
  Want me to go deeper on any module — e.g. a hand-traced single decision tree, the math of cyclical encoding, or
  how to actually clean that max_residual bug and retrain?