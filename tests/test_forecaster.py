"""Unit tests for the Holt early-warning forecaster (pure NumPy, no heavy deps)."""
from forecaster import RiskForecaster


def test_forecast_clamped_and_rising():
    fc = RiskForecaster(hop_sec=1.0)
    for r in [0.02, 0.03, 0.05, 0.07, 0.09]:
        fc.update(r)
    f = fc.forecast(4)
    assert 0.0 <= f <= 1.0
    assert fc.slope_per_sec() > 0          # rising trend detected
    assert f >= fc.history[-1]             # forecast extends the climb


def test_pre_alert_fires_before_crossing():
    fc = RiskForecaster(hop_sec=1.0)
    for r in [0.02, 0.03, 0.05, 0.07, 0.09]:   # below 0.10 but climbing
        fc.update(r)
    warn = fc.pre_alert(threshold=0.10, horizon_steps=4)
    assert warn is not None
    assert warn["forecast"] >= 0.10
    assert warn["lead_time_sec"] is not None and warn["lead_time_sec"] > 0


def test_no_pre_alert_when_falling():
    fc = RiskForecaster(hop_sec=1.0)
    for r in [0.5, 0.4, 0.3, 0.2]:
        fc.update(r)
    assert fc.pre_alert(threshold=0.10, horizon_steps=4) is None


def test_no_pre_alert_when_already_above():
    fc = RiskForecaster()
    for r in [0.2, 0.25, 0.3]:
        fc.update(r)
    # current already above threshold -> not a *pre*-alert
    assert fc.pre_alert(threshold=0.10, horizon_steps=4) is None
