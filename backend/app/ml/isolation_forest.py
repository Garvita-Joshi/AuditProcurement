"""
AuditAI — Isolation Forest trained on Autoencoder-reconstructed features.

This is stage 2 of the two-stage pipeline. The Isolation Forest operates on the
reconstructed feature space (autoencoder output), NOT on raw input features.
This makes it more robust to noisy OCR-derived features because anomalies are
detected in "what the model thinks normal looks like."
"""
import logging
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest

logger = logging.getLogger(__name__)


def train_isolation_forest(
    reconstructed_features: np.ndarray,
    config,
) -> IsolationForest:
    """
    Train an Isolation Forest on Autoencoder-reconstructed features.

    Args:
        reconstructed_features: 2D array from autoencoder output (n_samples, n_features).
        config: Config module with IF_* hyperparameters and TRAINED_MODELS_DIR.

    Returns:
        Trained IsolationForest model.
    """
    logger.info(
        "Training Isolation Forest: %d samples, contamination=%.3f, n_estimators=%d",
        reconstructed_features.shape[0],
        config.IF_CONTAMINATION,
        config.IF_N_ESTIMATORS,
    )

    model = IsolationForest(
        contamination=config.IF_CONTAMINATION,
        n_estimators=config.IF_N_ESTIMATORS,
        random_state=config.IF_RANDOM_STATE,
        n_jobs=-1,
    )
    model.fit(reconstructed_features)

    # Save model
    model_dir = Path(config.TRAINED_MODELS_DIR)
    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = str(model_dir / "isolation_forest.pkl")
    joblib.dump(model, model_path)
    logger.info("Isolation Forest saved to %s", model_path)

    return model


def load_isolation_forest(config) -> IsolationForest:
    """Load a trained Isolation Forest from disk."""
    model_path = str(Path(config.TRAINED_MODELS_DIR) / "isolation_forest.pkl")
    return joblib.load(model_path)


def predict_anomaly_scores(
    model: IsolationForest,
    reconstructed_features: np.ndarray,
) -> np.ndarray:
    """
    Compute anomaly scores from the Isolation Forest.

    sklearn's decision_function returns negative values for anomalies and positive
    for normal points. We negate and normalize to a 0-1 range where higher = more
    anomalous.

    Args:
        model: Trained IsolationForest.
        reconstructed_features: 2D array from autoencoder output.

    Returns:
        1D array of anomaly scores in [0, 1], one per sample.
    """
    raw_scores = model.decision_function(reconstructed_features)

    # Negate so that anomalies have higher scores
    negated = -raw_scores

    # Normalize to [0, 1]
    score_min = negated.min()
    score_max = negated.max()
    score_range = score_max - score_min

    if score_range == 0:
        return np.full(len(negated), 0.5)

    normalized = (negated - score_min) / score_range
    return normalized
