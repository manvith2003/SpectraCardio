"""
forecaster.py
-------------
Early-warning forecasting on the live risk stream.

The real-time analyzer emits a Brugada risk score every `hop` seconds. This
module treats that score as a time series and FORECASTS it a few steps ahead,
so the system can raise a PRE-ALERT *before* the risk actually crosses the
screening threshold -- the same idea a trading model uses to flag a move before
it fully plays out.

Method: Holt's linear (double-exponential) smoothing -- an online, trend-aware
forecaster that needs only the running level and trend, no batch refit:

    level_t  = a * y_t              + (1 - a) * (level_{t-1} + trend_{t-1})
    trend_t  = b * (level_t - lev_) + (1 - b) * trend_{t-1}
    forecast(h) = level_t + h * trend_t

It also tracks recent one-step errors to put an uncertainty band on the forecast,
and estimates the LEAD TIME (in seconds) until the projected threshold crossing.

Pure NumPy -- runs anywhere, no scipy/sklearn needed.

HONEST SCOPE: this forecasts the *model's risk signal* as it evolves while the
sliding window fills with (or scrolls across) ECG -- a streaming-analytics /
forecasting demonstration. It is not a validated clinical predictor of a future
cardiac event, and the research dataset (single 12 s snapshots) can't support that.
"""

import numpy as np


class RiskForecaster:
    def __init__(self, alpha=0.4, beta=0.3, hop_sec=1.0, max_hist=120):
        self.alpha = alpha          # level smoothing
        self.beta = beta            # trend smoothing
        self.hop_sec = hop_sec      # seconds between scores (for lead-time units)
        self.level = None
        self.trend = 0.0
        self.history = []           # observed risks
        self.errors = []            # one-step forecast errors (for the band)
        self.max_hist = max_hist

    def update(self, risk):
        """Feed the latest observed risk; updates level + trend online."""
        if self.level is None:
            self.level = risk
            self.trend = 0.0
        else:
            # one-step forecast error for this new point (before updating)
            pred1 = self.level + self.trend
            self.errors.append(risk - pred1)
            self.errors = self.errors[-self.max_hist:]

            prev_level = self.level
            self.level = self.alpha * risk + (1 - self.alpha) * (self.level + self.trend)
            self.trend = self.beta * (self.level - prev_level) + (1 - self.beta) * self.trend

        self.history.append(risk)
        self.history = self.history[-self.max_hist:]

    def forecast(self, horizon_steps):
        """Predicted risk `horizon_steps` ahead (clamped to [0, 1])."""
        if self.level is None:
            return 0.0
        return float(np.clip(self.level + horizon_steps * self.trend, 0.0, 1.0))

    def band(self, horizon_steps, z=1.64):
        """Approx (lo, hi) uncertainty band around the horizon forecast.
        Error grows ~sqrt(h); z=1.64 ~ 90% one-sided."""
        f = self.forecast(horizon_steps)
        if len(self.errors) < 3:
            return f, f
        s = np.std(self.errors) * np.sqrt(max(horizon_steps, 1))
        return float(np.clip(f - z * s, 0, 1)), float(np.clip(f + z * s, 0, 1))

    def slope_per_sec(self):
        """Current trend expressed as risk change per second."""
        return float(self.trend / self.hop_sec)

    def steps_to_cross(self, threshold):
        """Projected steps until the trend line reaches `threshold`.
        Returns None if not heading toward a crossing."""
        if self.level is None or self.trend <= 1e-9:
            return None
        if self.level >= threshold:
            return 0
        k = (threshold - self.level) / self.trend
        return k if k > 0 else None

    def lead_time_sec(self, threshold):
        k = self.steps_to_cross(threshold)
        return None if k is None else k * self.hop_sec

    def pre_alert(self, threshold, horizon_steps):
        """Early-warning decision.

        Returns a dict describing the warning, or None. Fires when the current
        risk is still BELOW threshold but the forecast at the horizon is at/above
        it and the trend is rising -- i.e., we expect a crossing soon.
        """
        if self.level is None:
            return None
        current = self.history[-1]
        fcast = self.forecast(horizon_steps)
        if current < threshold and fcast >= threshold and self.trend > 0:
            return {
                "current": current,
                "forecast": fcast,
                "horizon_steps": horizon_steps,
                "slope_per_sec": self.slope_per_sec(),
                "lead_time_sec": self.lead_time_sec(threshold),
            }
        return None
