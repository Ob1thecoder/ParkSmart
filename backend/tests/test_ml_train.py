import pytest
from app.ml.train import train


def test_train_raises_on_insufficient_data(seeded_db, tmp_path):
    # seeded_db has car parks but no occupancy_history rows.
    with pytest.raises(RuntimeError, match="training rows"):
        train(seeded_db, tmp_path / "occupancy_v1.pkl", tmp_path / "eval_report.md")
