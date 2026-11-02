"""Procurement-specific AE/IF inference. Expense artifacts are never relabeled.

An optional procurement bundle must contain these feature names, an AE state,
scaler, Isolation Forest, and sorted validation score reference arrays. No online
retraining or per-request normalization is performed.
"""
import os
from pathlib import Path
import numpy as np

FEATURE_NAMES = ["amount_log", "item_count", "quantity_total", "delivery_ratio", "tax_ratio", "po_difference_ratio", "supplier_history_count", "supplier_amount_ratio"]


def features(terms, approved, historical_amounts):
    total = float(terms.total)
    history = [float(x) for x in historical_amounts]
    return np.array([np.log1p(total), len(terms.items), sum(x.quantity for x in terms.items),
                     float(terms.delivery) / max(total, 1), float(terms.tax) / max(total, 1),
                     abs(total - float(approved.total)) / max(float(approved.total), 1),
                     len(history), total / max(float(np.median(history)), 1) if history else 0], dtype=float)


def assess(terms, approved, historical_amounts):
    from backend.app.config import TRAINED_MODELS_DIR
    bundle_path = Path(os.getenv("PROCUREMENT_MODEL_BUNDLE", str(TRAINED_MODELS_DIR / "procurement_bundle.joblib")))
    if not bundle_path.is_file():
        return {"status": "unavailable", "reason": "No compatible procurement model bundle is installed.",
                "model": "Autoencoder + Isolation Forest", "score": None}
    try:
        import joblib
        import torch
        from backend.app.ml.autoencoder import ExpenseAutoencoder
        bundle = joblib.load(bundle_path)
        if bundle["feature_names"] != FEATURE_NAMES:
            raise ValueError("Feature schema does not match procurement-v1.")
        x = features(terms, approved, historical_amounts).reshape(1, -1)
        x = bundle["scaler"].transform(x)
        model = ExpenseAutoencoder(len(FEATURE_NAMES), bundle["latent_dim"])
        model.load_state_dict(bundle["ae_state"])
        model.eval()
        with torch.no_grad():
            reconstructed = model(torch.tensor(x, dtype=torch.float32)).numpy()
        ae_raw = float(np.mean((x - reconstructed) ** 2))
        if bundle.get("if_input") != "decoded":
            raise ValueError("Procurement bundle must use decoded AE features for Isolation Forest.")
        if_raw = float(-bundle["isolation_forest"].score_samples(reconstructed)[0])
        def percentile(value, reference):
            reference = np.asarray(reference)
            if reference.size < 20 or not np.isfinite(reference).all() or np.any(np.diff(reference) < 0):
                raise ValueError("Validation reference must be sorted, finite, and contain at least 20 values.")
            return float(np.searchsorted(reference, value, side="right") / len(reference))
        ae_score = percentile(ae_raw, bundle["ae_reference"])
        if_score = percentile(if_raw, bundle["if_reference"])
        weight = bundle.get("ae_weight", .4)
        score = weight * ae_score + (1 - weight) * if_score
        return {"status": "review" if score >= bundle.get("threshold", .95) else "assessed", "score": round(score, 4),
                "autoencoder_percentile": round(ae_score, 4), "isolation_forest_percentile": round(if_score, 4),
                "version": bundle.get("version", "procurement-v1"), "training_source": bundle.get("training_source", "unspecified"), "model": "Autoencoder + Isolation Forest",
                "note": "Anomaly percentile, not a fraud probability."}
    except Exception:
        return {"status": "unavailable", "reason": "Model bundle could not be validated. Check its feature schema and artifacts.", "score": None}
