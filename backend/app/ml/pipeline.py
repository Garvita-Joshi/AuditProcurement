"""
AuditAI — Two-stage fraud scoring pipeline orchestrator.

Pipeline architecture:
  1. Raw features → Autoencoder → Reconstructed features
  2. Reconstructed features → Isolation Forest → Anomaly scores
  3. Reconstruction error (input vs decoded) + IF anomaly score → Combined fraud score

The combination logic:
  final_score = α × normalized_reconstruction_error + (1 - α) × normalized_IF_score

  α = 0.4 (from config.SCORE_ALPHA). Reconstruction error is weighted lower because
  the Isolation Forest already operates on the reconstructed space and thus implicitly
  captures reconstruction quality. The reconstruction error adds a direct signal for
  gross distortions that IF might miss.

Both individual scores and the combined score are logged to the database independently.
"""
import logging
from typing import Dict, List, Optional

import numpy as np

from backend.app.ml.autoencoder import (
    ExpenseAutoencoder,
    compute_reconstruction_error,
    get_reconstructed_output,
    load_autoencoder,
    train_autoencoder,
)
from backend.app.ml.isolation_forest import (
    load_isolation_forest,
    predict_anomaly_scores,
    train_isolation_forest,
)

logger = logging.getLogger(__name__)


def _normalize_scores(scores: np.ndarray) -> np.ndarray:
    """Min-max normalize scores to [0, 1]."""
    s_min = scores.min()
    s_max = scores.max()
    s_range = s_max - s_min
    if s_range == 0:
        return np.full(len(scores), 0.5)
    return (scores - s_min) / s_range


def train_pipeline(
    feature_matrix: np.ndarray,
    feature_names: List[str],
    config,
) -> dict:
    """
    Train the full two-stage pipeline.

    Steps:
      1. Train Autoencoder on raw feature matrix
      2. Get reconstructed output from trained Autoencoder
      3. Train Isolation Forest on reconstructed output

    Args:
        feature_matrix: 2D numpy array (n_samples, n_features).
        feature_names: List of feature names matching columns.
        config: Config module with hyperparameters.

    Returns:
        Dict with keys: autoencoder, isolation_forest, scaler, metadata, feature_names.
    """
    logger.info("Training two-stage pipeline on %d samples, %d features",
                feature_matrix.shape[0], feature_matrix.shape[1])

    # Stage 1: Train autoencoder
    ae_model, scaler = train_autoencoder(feature_matrix, config)

    # Get reconstructed output from autoencoder
    _, _, metadata = load_autoencoder(config)
    reconstructed = get_reconstructed_output(ae_model, feature_matrix, scaler, metadata)

    # Stage 2: Train Isolation Forest on reconstructed features
    if_model = train_isolation_forest(reconstructed, config)

    logger.info("Two-stage pipeline training complete.")

    return {
        "autoencoder": ae_model,
        "isolation_forest": if_model,
        "scaler": scaler,
        "metadata": metadata,
        "feature_names": feature_names,
    }


def score_claims(
    feature_matrix: np.ndarray,
    pipeline_artifacts: dict,
    config,
) -> List[Dict]:
    """
    Score claims through the two-stage pipeline.

    Steps:
      1. Pass features through autoencoder → reconstructed output
      2. Compute reconstruction error (MSE of input vs reconstructed)
      3. Pass reconstructed output into Isolation Forest → anomaly scores
      4. Normalize both scores to [0, 1]
      5. Combine: final = α × recon_error + (1-α) × IF_score
      6. Flag claims exceeding threshold

    Args:
        feature_matrix: 2D numpy array of raw features.
        pipeline_artifacts: Dict from train_pipeline() or load_pipeline().
        config: Config module with SCORE_ALPHA and FRAUD_SCORE_THRESHOLD.

    Returns:
        List of dicts, one per claim:
          {reconstruction_error, isolation_forest_score, combined_fraud_score, is_flagged}
    """
    ae_model = pipeline_artifacts["autoencoder"]
    if_model = pipeline_artifacts["isolation_forest"]
    scaler = pipeline_artifacts["scaler"]
    metadata = pipeline_artifacts["metadata"]

    # Step 1: Reconstruct through autoencoder
    reconstructed = get_reconstructed_output(ae_model, feature_matrix, scaler, metadata)

    # Step 2: Compute reconstruction error
    # Normalize original features the same way for fair comparison
    scaled = scaler.transform(feature_matrix)
    scaled = np.clip(scaled, -5, 5)
    data_min = metadata["data_min"]
    data_max = metadata["data_max"]
    data_range = data_max - data_min
    data_range[data_range == 0] = 1.0
    scaled_01 = (scaled - data_min) / data_range

    recon_errors = compute_reconstruction_error(scaled_01, reconstructed)

    # Step 3: Isolation Forest anomaly scores on reconstructed features
    if_scores = predict_anomaly_scores(if_model, reconstructed)

    # Step 4: Normalize reconstruction errors to [0, 1]
    norm_recon = _normalize_scores(recon_errors)

    # Step 5: Combine scores
    alpha = config.SCORE_ALPHA
    combined = alpha * norm_recon + (1 - alpha) * if_scores

    # Step 6: Flag claims above threshold
    threshold = config.FRAUD_SCORE_THRESHOLD

    results = []
    for i in range(len(feature_matrix)):
        results.append({
            "reconstruction_error": round(float(norm_recon[i]), 6),
            "isolation_forest_score": round(float(if_scores[i]), 6),
            "combined_fraud_score": round(float(combined[i]), 6),
            "is_flagged": bool(combined[i] > threshold),
        })

    flagged_count = sum(1 for r in results if r["is_flagged"])
    logger.info(
        "Scored %d claims: %d flagged (%.1f%%), threshold=%.2f, α=%.2f",
        len(results), flagged_count, 100 * flagged_count / max(len(results), 1),
        threshold, alpha,
    )

    return results


def load_pipeline(config) -> Optional[dict]:
    """
    Load all saved pipeline artifacts from disk.

    Returns:
        Dict with autoencoder, isolation_forest, scaler, metadata, or None if not found.
    """
    try:
        ae_model, scaler, metadata = load_autoencoder(config)
        if_model = load_isolation_forest(config)

        return {
            "autoencoder": ae_model,
            "isolation_forest": if_model,
            "scaler": scaler,
            "metadata": metadata,
        }
    except FileNotFoundError as e:
        logger.warning("Pipeline artifacts not found: %s", e)
        return None
    except Exception as e:
        logger.error("Failed to load pipeline: %s", e)
        return None
