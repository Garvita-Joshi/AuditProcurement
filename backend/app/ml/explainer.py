"""
AuditAI — SHAP explainability for the Isolation Forest.

Computes SHAP values for each flagged claim's feature vector (in the reconstructed
feature space) using TreeExplainer, then maps back to human-readable feature names.
"""
import logging
from typing import Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


def compute_shap_values(
    isolation_forest_model,
    reconstructed_features: np.ndarray,
    feature_names: List[str],
    claim_indices: Optional[List[int]] = None,
) -> List[Dict[str, float]]:
    """
    Compute SHAP values for claims using the Isolation Forest model.

    Args:
        isolation_forest_model: Trained sklearn IsolationForest.
        reconstructed_features: 2D array from autoencoder output (n_samples, n_features).
        feature_names: List of feature names matching columns.
        claim_indices: If provided, only compute SHAP for these row indices.
                       If None, computes for all rows.

    Returns:
        List of dicts mapping feature_name → SHAP value for each claim.
        Empty dicts on failure.
    """
    try:
        import shap

        # Select subset if indices provided
        if claim_indices is not None:
            subset = reconstructed_features[claim_indices]
        else:
            subset = reconstructed_features
            claim_indices = list(range(len(reconstructed_features)))

        if len(subset) == 0:
            return []

        # Use TreeExplainer for the Isolation Forest
        explainer = shap.TreeExplainer(isolation_forest_model)
        shap_values = explainer.shap_values(subset)

        # Map to feature names
        results = []
        for i in range(len(subset)):
            if len(feature_names) != shap_values.shape[1]:
                # Feature dimension mismatch — return raw indices
                shap_dict = {
                    f"feature_{j}": round(float(shap_values[i, j]), 6)
                    for j in range(shap_values.shape[1])
                }
            else:
                shap_dict = {
                    feature_names[j]: round(float(shap_values[i, j]), 6)
                    for j in range(len(feature_names))
                }
            results.append(shap_dict)

        logger.info("Computed SHAP values for %d claims.", len(results))
        return results

    except ImportError:
        logger.warning("SHAP library not available. Returning empty explanations.")
        count = len(claim_indices) if claim_indices else len(reconstructed_features)
        return [{} for _ in range(count)]
    except Exception as e:
        logger.error("SHAP computation failed: %s", e)
        count = len(claim_indices) if claim_indices else len(reconstructed_features)
        return [{} for _ in range(count)]


def get_top_features(
    shap_dict: Dict[str, float],
    top_n: int = 5,
) -> List[Dict]:
    """
    Get the top N most influential features from a SHAP value dict.

    Args:
        shap_dict: Dict mapping feature_name → SHAP value.
        top_n: Number of top features to return.

    Returns:
        List of dicts: [{feature, value, direction}, ...] sorted by absolute value.
        direction is 'positive' (pushes toward fraud) or 'negative' (pushes toward normal).
    """
    if not shap_dict:
        return []

    sorted_features = sorted(
        shap_dict.items(),
        key=lambda x: abs(x[1]),
        reverse=True,
    )[:top_n]

    return [
        {
            "feature": name,
            "value": round(value, 6),
            "direction": "positive" if value > 0 else "negative",
        }
        for name, value in sorted_features
    ]
