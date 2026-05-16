from datetime import datetime
from app.services.simulator import simulated_available, BASELINES, SIM_CAR_PARK_IDS


def test_all_sim_ids_covered():
    assert set(SIM_CAR_PARK_IDS) == set(BASELINES.keys())


def test_deterministic_same_result_for_same_input():
    dt = datetime(2026, 5, 15, 13, 0, 0)
    result_a = simulated_available("sim_westfield", dt)
    result_b = simulated_available("sim_westfield", dt)
    assert result_a == result_b
    assert isinstance(result_a, int)


def test_result_within_capacity():
    dt = datetime(2026, 5, 15, 13, 0, 0)
    result = simulated_available("sim_westfield", dt)
    capacity = BASELINES["sim_westfield"]["capacity"]
    assert 0 <= result <= capacity


def test_minutes_do_not_affect_result():
    dt_top = datetime(2026, 5, 15, 13, 0, 0)
    dt_mid = datetime(2026, 5, 15, 13, 45, 0)
    assert simulated_available("sim_westfield", dt_top) == simulated_available("sim_westfield", dt_mid)


def test_offpeak_has_more_available_than_peak():
    peak    = simulated_available("sim_westfield", datetime(2026, 5, 13, 13, 0))  # Wed 1pm
    offpeak = simulated_available("sim_westfield", datetime(2026, 5, 13, 3, 0))   # Wed 3am
    assert offpeak > peak


def test_weekend_busier_for_shopping_carpark():
    # Westfield has more demand on weekend daytime
    weekday = simulated_available("sim_westfield", datetime(2026, 5, 13, 13, 0))  # Wednesday
    weekend = simulated_available("sim_westfield", datetime(2026, 5, 16, 13, 0))  # Saturday
    assert weekend < weekday


def test_commuter_park_busier_on_weekday_morning():
    # Victoria Ave CP is commuter-pattern: busy Mon–Fri morning, quiet weekend
    weekday = simulated_available("sim_victoria_ave_cp", datetime(2026, 5, 13, 9, 0))
    weekend = simulated_available("sim_victoria_ave_cp", datetime(2026, 5, 16, 9, 0))
    assert weekday < weekend


def test_unknown_car_park_raises():
    import pytest
    with pytest.raises(KeyError):
        simulated_available("not_a_car_park", datetime(2026, 5, 15, 13, 0))
