"""Train the TfNSW occupancy model + residual confidence model.

Run:  python -m app.ml.train
Reads real history from occupancy_history, fits two XGBoost regressors, and
writes models/occupancy_v1.pkl + models/eval_report.md.
"""
import argparse
import logging
import pickle
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from xgboost import XGBRegressor

from app.config import settings as _settings
from app.db import get_connection
from app.ml.features import FEATURE_COLUMNS, TFNSW_CAR_PARK_IDS, build_training_frame

log = logging.getLogger(__name__)

MODEL_VERSION = "xgboost-v1"
_MIN_TRAINING_ROWS = 200

_XGB_PARAMS = dict(
    n_estimators=200,
    max_depth=4,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    random_state=42,
)


def _load_history(db_path: Path) -> list[dict]:
    placeholders = ",".join("?" for _ in TFNSW_CAR_PARK_IDS)
    with get_connection(db_path) as con:
        rows = con.execute(
            f"SELECT car_park_id, ts, available, total_spots FROM occupancy_history "
            f"WHERE car_park_id IN ({placeholders})",
            TFNSW_CAR_PARK_IDS,
        ).fetchall()
    return [dict(r) for r in rows]


def train(
    db_path: Path, model_out: Path, report_out: Path, holdout_days: int = 7
) -> dict:
    """Fit the occupancy + residual models and persist the bundle. Returns metrics."""
    frame = build_training_frame(_load_history(db_path))
    if len(frame) < _MIN_TRAINING_ROWS:
        raise RuntimeError(
            f"Only {len(frame)} training rows (need >= {_MIN_TRAINING_ROWS}). "
            "Collect more TfNSW history before training."
        )

    cutoff = frame["ts"].max() - pd.Timedelta(days=holdout_days)
    train_df = frame[frame["ts"] <= cutoff]
    val_df = frame[frame["ts"] > cutoff]
    if len(train_df) < _MIN_TRAINING_ROWS:
        raise RuntimeError(
            f"Only {len(train_df)} rows left after the {holdout_days}-day holdout "
            f"(need >= {_MIN_TRAINING_ROWS})."
        )

    X_train = train_df[FEATURE_COLUMNS]
    y_train = train_df["target"].to_numpy()

    occ_model = XGBRegressor(**_XGB_PARAMS)
    occ_model.fit(X_train, y_train)

    abs_resid = np.abs(y_train - occ_model.predict(X_train))
    resid_model = XGBRegressor(**_XGB_PARAMS)
    resid_model.fit(X_train, abs_resid)
    max_residual = float(abs_resid.max()) if len(abs_resid) else 1.0

    if len(val_df):
        val_pred = occ_model.predict(val_df[FEATURE_COLUMNS])
        val_mae = float(np.abs(val_df["target"].to_numpy() - val_pred).mean())
    else:
        val_mae = float("nan")

    bundle = {
        "occupancy_model": occ_model,
        "residual_model": resid_model,
        "feature_columns": FEATURE_COLUMNS,
        "train_mean_occupancy": float(y_train.mean()),
        "max_residual": max_residual,
        "model_version": MODEL_VERSION,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "n_train": int(len(train_df)),
        "n_val": int(len(val_df)),
    }

    model_out.parent.mkdir(parents=True, exist_ok=True)
    with model_out.open("wb") as fh:
        pickle.dump(bundle, fh)

    report_out.parent.mkdir(parents=True, exist_ok=True)
    report_out.write_text(
        "# Occupancy Model Evaluation\n\n"
        f"- Model version: {MODEL_VERSION}\n"
        f"- Trained at: {bundle['trained_at']}\n"
        f"- Training rows: {bundle['n_train']}\n"
        f"- Validation rows: {bundle['n_val']}\n"
        f"- Validation MAE (occupancy fraction): {val_mae:.4f}\n"
        f"- Max training residual: {max_residual:.4f}\n"
    )
    log.info("Saved model to %s (validation MAE %.4f)", model_out, val_mae)
    return {"val_mae": val_mae, "n_train": bundle["n_train"], "n_val": bundle["n_val"]}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Train the TfNSW occupancy model.")
    parser.add_argument("--holdout-days", type=int, default=7)
    args = parser.parse_args()

    base = Path(__file__).parent.parent.parent / "models"
    result = train(
        _settings.db_path,
        base / "occupancy_v1.pkl",
        base / "eval_report.md",
        holdout_days=args.holdout_days,
    )
    print(f"Validation MAE: {result['val_mae']:.4f}  "
          f"(train={result['n_train']}, val={result['n_val']})")


if __name__ == "__main__":
    main()
