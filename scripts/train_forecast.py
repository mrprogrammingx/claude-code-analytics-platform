"""Small forecasting trainer for the demo notebook.

This script trains a trivial model to predict `total_tokens` from `prompt_length`
and `model` using either scikit-learn (if installed) or a numpy least-squares
fallback. The trained model is persisted using joblib to `models/forecast.joblib`.
"""
from pathlib import Path
import pickle

import pandas as pd
import numpy as np

MODELS_DIR = Path("models")
MODELS_DIR.mkdir(parents=True, exist_ok=True)
MODEL_PATH = MODELS_DIR / "forecast.joblib"

try:
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.model_selection import train_test_split
    have_sklearn = True
except Exception:
    have_sklearn = False

DB_PATH = Path("analytics.db")


def load_sample(n=1000):
    if DB_PATH.exists():
        try:
            import duckdb

            con = duckdb.connect(str(DB_PATH), read_only=True)
            df = con.execute(
                "SELECT prompt_length, model, total_tokens FROM telemetry_events LIMIT ?",
                [n],
            ).fetchdf()
            con.close()
            if not df.empty:
                return df
        except Exception:
            pass
    # fallback synth
    np.random.seed(42)
    prompt_len = np.random.poisson(100, size=n) + np.random.randint(0, 50, size=n)
    models = np.random.choice(["claude-v1", "claude-instant", "gpt-4"], size=n)
    model_effect = {"claude-v1": 1.0, "claude-instant": 0.9, "gpt-4": 1.2}
    total_tokens = (prompt_len * np.array([model_effect[m] for m in models]) + np.random.normal(0, 20, size=n)).astype(int)
    return pd.DataFrame({"prompt_length": prompt_len, "model": models, "total_tokens": total_tokens})


def featurize(df: pd.DataFrame):
    df = df.copy()
    df["prompt_length"] = pd.to_numeric(df["prompt_length"], errors="coerce").fillna(0).astype(int)
    df["model_code"] = df["model"].astype("category").cat.codes
    X = df[["prompt_length", "model_code"]].values
    y = df["total_tokens"].values
    return X, y


def train_and_persist():
    df = load_sample(2000)
    X, y = featurize(df)
    if have_sklearn:
        model = RandomForestRegressor(n_estimators=50, random_state=42)
        model.fit(X, y)
        # Persist with joblib if available
        try:
            import joblib

            joblib.dump(model, MODEL_PATH)
            print("Saved model to", MODEL_PATH)
            return MODEL_PATH
        except Exception:
            # fallback to pickle
            with open(MODEL_PATH, "wb") as f:
                pickle.dump(model, f)
            print("Saved model (pickle) to", MODEL_PATH)
            return MODEL_PATH
    else:
        # simple linear least squares
        Xb = np.column_stack([np.ones(len(X)), X])
        coef, *_ = np.linalg.lstsq(Xb, y, rcond=None)
        # persist coefficients
        with open(MODEL_PATH, "wb") as f:
            pickle.dump({"coef": coef.tolist()}, f)
        print("Saved linear model to", MODEL_PATH)
        return MODEL_PATH


if __name__ == "__main__":
    train_and_persist()
