"""Model inference. No Django imports so train.py can reuse feats().
Everything is expressed relative to each station's flood threshold (95th percentile of discharge)."""
import os
from pathlib import Path
import numpy as np, joblib

MODEL_DIR = Path(os.environ.get("MODEL_DIR", Path(__file__).resolve().parent.parent / "ml_models"))
CLASSES = ["LOW", "MEDIUM", "HIGH"]
WINDOW, HORIZON = 14, 3          # 14 days of history -> forecast 3 days ahead
MEDIUM_AT, HIGH_AT = 0.75, 1.0   # fractions of the flood threshold
VERSION = "v3-forecast-rain"
_cache = {}

def feats(rain, q, pred, fut):
    """rain: (n,14) mm/day; q: (n,14) discharge / threshold; pred: (n,) predicted q; fut: (n,3) rain over the next 3 days."""
    return np.column_stack([rain[:, -3:].sum(1), rain[:, -7:].sum(1), rain.sum(1), fut.sum(1), q[:, -1], q[:, -1] - q[:, -4], pred])

def _load():
    if not _cache:
        import tensorflow as tf
        _cache["lstm"] = tf.keras.models.load_model(MODEL_DIR / "lstm.keras")
        _cache["rf"] = joblib.load(MODEL_DIR / "rf.joblib")
    return _cache

def predict(rain_14, discharge_14, threshold, future_rain=None):
    """Returns (predicted discharge m3/s in HORIZON days, risk label, probability of HIGH)."""
    m = _load()
    fut = np.array(future_rain if future_rain is not None else [0.0] * HORIZON, float)[None]
    rain, q = np.array(rain_14, float)[None], np.clip(np.array(discharge_14, float)[None] / threshold, 0, 5)
    pred = float(m["lstm"].predict([np.stack([rain / 50, q], -1), fut / 50], verbose=0)[0, 0]) * 5
    proba = dict(zip(m["rf"].classes_, m["rf"].predict_proba(feats(rain, q, np.array([pred]), fut))[0]))
    return pred * threshold, CLASSES[int(max(proba, key=proba.get))], float(proba.get(2, 0.0))
