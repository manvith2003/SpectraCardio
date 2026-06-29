"""Real-time ECG streaming + analysis package for SpectraCardio.

Turns the batch screen into a live, sliding-window pipeline:

    SOURCE (device / socket / file replay)  ->  SLIDING-WINDOW FFT ANALYZER
        ->  SCORER (Random Forest / logistic fallback)  ->  LIVE RISK + ALERTS

The SOURCE is pluggable: replay a recording at its true 100 Hz rate for a demo,
or point a TCP socket / stdin at a real ECG device feed in production. The
analyzer and scorer don't care where samples come from.
"""
