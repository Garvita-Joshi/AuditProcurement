"""
AuditAI — API endpoints for ML-based fraud scoring and dashboard summaries.
"""
import logging
from collections import defaultdict
from typing import Any, Dict

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app import config
from backend.app.db import get_db
from backend.app.features.engineer import compute_features_batch
from backend.app.ml.explainer import compute_shap_values, get_top_features
from backend.app.ml.pipeline import load_pipeline, score_claims, train_pipeline
from backend.app.models.expense import ExpenseClaim, FraudPrediction, Case, CaseAuditTrail
from backend.app.api.analytics import get_case_cycle_metrics

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/fraud", tags=["Fraud"])


@router.get("/summary", response_model=Dict[str, Any])
def get_fraud_summary(db: Session = Depends(get_db)):
    """Get dashboard summary statistics."""
    total_claims = db.query(ExpenseClaim).count()
    if total_claims == 0:
        return {
            "total_claims": 0,
            "flagged_count": 0,
            "fraud_rate": 0.0,
            "average_score": 0.0,
            "score_distribution": {},
            "recent_flagged": [],
            "fraud_over_time": [],
            "kpis": {
                "avg_time_to_disposition_seconds": 0.0,
                "false_positive_rate": 0.0,
                "total_disposed_cases": 0
            }
        }

    # Get predictions
    predictions = db.query(FraudPrediction).all()
    flagged_count = sum(1 for p in predictions if p.is_flagged)
    fraud_rate = (flagged_count / total_claims) * 100 if total_claims > 0 else 0.0

    scores = [p.combined_fraud_score for p in predictions if p.combined_fraud_score is not None]
    average_score = sum(scores) / len(scores) if scores else 0.0

    # Score distribution histogram (10 buckets from 0 to 1)
    distribution = {f"{i/10:.1f}-{i/10+0.1:.1f}": 0 for i in range(10)}
    for s in scores:
        bucket = min(int(s * 10), 9)
        distribution[f"{bucket/10:.1f}-{bucket/10+0.1:.1f}"] += 1

    # Recent flagged claims
    recent_flagged_db = (
        db.query(ExpenseClaim)
        .join(FraudPrediction)
        .filter(FraudPrediction.is_flagged == True)
        .order_by(FraudPrediction.predicted_at.desc())
        .limit(20) # Increase limit to support frontend filters
        .all()
    )
    
    # Import get_closest_vendor from claims to get typosquats dynamically
    from backend.app.api.claims import get_closest_vendor

    recent_flagged = []
    for c in recent_flagged_db:
        closest_match, match_ratio = get_closest_vendor(c.vendor_name)
        if match_ratio >= 1.0 or match_ratio < 0.70:
            closest_match = None
            match_ratio = 0.0
            
        recent_flagged.append({
            "id": c.id,
            "claim_id": c.claim_id,
            "vendor_name": c.vendor_name,
            "employee_name": c.employee_name,
            "claimed_amount": float(c.claimed_amount),
            "claimed_date": c.claimed_date.isoformat(),
            "fraud_score": c.prediction.combined_fraud_score,
            "status": c.status,
            "case_status": c.case.status if c.case else "none",
            "closest_vendor_match": closest_match,
            "vendor_similarity_score": match_ratio if closest_match else None,
        })

    # Fraud over time (monthly count of flagged claims)
    time_series = defaultdict(lambda: {"total": 0, "flagged": 0})
    for c in db.query(ExpenseClaim).all():
        month = c.claimed_date.strftime("%Y-%m")
        time_series[month]["total"] += 1
        if c.prediction and c.prediction.is_flagged:
            time_series[month]["flagged"] += 1

    fraud_over_time = [
        {
            "date": month,
            "count": data["total"],
            "flagged_count": data["flagged"],
            "rate": round(data["flagged"] / data["total"] * 100, 1),
        }
        for month, data in sorted(time_series.items())
    ]

    # Fetch Case management cycle metrics (KPIs)
    kpis = get_case_cycle_metrics(db)

    return {
        "total_claims": total_claims,
        "flagged_count": flagged_count,
        "fraud_rate": round(fraud_rate, 2),
        "average_score": round(average_score, 4),
        "score_distribution": distribution,
        "recent_flagged": recent_flagged,
        "fraud_over_time": fraud_over_time,
        "kpis": kpis
    }


@router.post("/train", status_code=status.HTTP_200_OK)
def train_models(db: Session = Depends(get_db)):
    """Train the Autoencoder and Isolation Forest on all available claims."""
    claims = db.query(ExpenseClaim).all()
    if len(claims) < 50:
        raise HTTPException(400, "Need at least 50 claims to train models.")

    # Convert claims to dicts for feature engineering
    claim_dicts = []
    for c in claims:
        d = {
            "claim_id": c.claim_id,
            "employee_id": c.employee_id,
            "claimed_amount": float(c.claimed_amount),
            "vendor_name": c.vendor_name,
            "claimed_date": c.claimed_date,
            "category": c.category,
            "ocr_amount": float(c.receipt.ocr_result.extracted_amount) if (c.receipt and c.receipt.ocr_result and c.receipt.ocr_result.extracted_amount is not None) else None,
        }
        claim_dicts.append(d)

    # Get known vendors (vendors appearing > 3 times)
    vendor_counts = {}
    for c in claims:
        vendor_counts[c.vendor_name] = vendor_counts.get(c.vendor_name, 0) + 1
    known_vendors = [v for v, count in vendor_counts.items() if count > 3]

    # Compute features
    features_list, feature_names = compute_features_batch(claim_dicts, known_vendors)
    
    # Convert to matrix
    feature_matrix = np.array([[f[name] for name in feature_names] for f in features_list])

    try:
        train_pipeline(feature_matrix, feature_names, config)
        return {"status": "success", "message": "Models trained successfully."}
    except Exception as e:
        logger.error("Training failed: %s", e)
        raise HTTPException(500, f"Training failed: {e}")


@router.post("/score", status_code=status.HTTP_200_OK)
def score_all_claims(db: Session = Depends(get_db)):
    """Score all unscored claims through the pipeline."""
    pipeline = load_pipeline(config)
    if not pipeline:
        raise HTTPException(500, "Pipeline models not found. Please train first.")

    # Get unscored claims
    claims = db.query(ExpenseClaim).filter(
        (ExpenseClaim.status == "pending") | (ExpenseClaim.status == "processing")
    ).all()

    if not claims:
        return {"status": "success", "message": "No claims to score.", "scored_count": 0, "flagged_count": 0}

    # Need all claims for context-aware features (like duplicates, z-scores)
    all_claims = db.query(ExpenseClaim).all()
    all_dicts = []
    for c in all_claims:
        all_dicts.append({
            "claim_id": c.claim_id,
            "employee_id": c.employee_id,
            "claimed_amount": float(c.claimed_amount),
            "vendor_name": c.vendor_name,
            "claimed_date": c.claimed_date,
            "category": c.category,
            "ocr_amount": float(c.receipt.ocr_result.extracted_amount) if (c.receipt and c.receipt.ocr_result and c.receipt.ocr_result.extracted_amount is not None) else None,
        })

    vendor_counts = {}
    for c in all_claims:
        vendor_counts[c.vendor_name] = vendor_counts.get(c.vendor_name, 0) + 1
    known_vendors = [v for v, count in vendor_counts.items() if count > 3]

    target_dicts = [d for d in all_dicts if any(c.claim_id == d["claim_id"] for c in claims)]
    
    # Compute features for targets
    features_list, feature_names = compute_features_batch(target_dicts, known_vendors)
    feature_matrix = np.array([[f[name] for name in feature_names] for f in features_list])

    # Score claims
    results = score_claims(feature_matrix, pipeline, config)

    # Compute SHAP for flagged claims
    # We only compute SHAP for the ones that actually got flagged to save time
    flagged_indices = [i for i, res in enumerate(results) if res["is_flagged"]]
    
    # We need reconstructed features for SHAP
    from backend.app.ml.autoencoder import get_reconstructed_output
    ae_model = pipeline["autoencoder"]
    scaler = pipeline["scaler"]
    metadata = pipeline["metadata"]
    if_model = pipeline["isolation_forest"]
    
    reconstructed = get_reconstructed_output(ae_model, feature_matrix, scaler, metadata)
    
    shap_results = compute_shap_values(
        if_model, 
        reconstructed, 
        feature_names, 
        claim_indices=flagged_indices if flagged_indices else None
    )

    # Save to DB
    flagged_count = 0
    shap_idx = 0
    
    for i, claim in enumerate(claims):
        res = results[i]
        is_flagged = res["is_flagged"]
        if is_flagged:
            flagged_count += 1
            
        shap_vals = {}
        if is_flagged and shap_idx < len(shap_results):
            # Convert full shap dict to top 5
            top_features = get_top_features(shap_results[shap_idx], top_n=5)
            shap_vals = {f["feature"]: f["value"] for f in top_features}
            shap_idx += 1

        # Delete existing prediction if any (shouldn't happen based on query)
        if claim.prediction:
            db.delete(claim.prediction)
            
        pred = FraudPrediction(
            claim_id=claim.claim_id,
            reconstruction_error=res["reconstruction_error"],
            isolation_forest_score=res["isolation_forest_score"],
            combined_fraud_score=res["combined_fraud_score"],
            is_flagged=is_flagged,
            shap_values=shap_vals if is_flagged else None,
            feature_values=features_list[i],
        )
        db.add(pred)
        
        claim.status = "flagged" if is_flagged else "scored"

        # Create Case & Audit Trail if flagged
        if is_flagged:
            # Check if case already exists to prevent duplicate entries
            case = db.query(Case).filter(Case.claim_id == claim.claim_id).first()
            if not case:
                case = Case(
                    claim_id=claim.claim_id,
                    status="open",
                )
                db.add(case)
                db.flush() # Flush to get case.id
                
                trail = CaseAuditTrail(
                    case_id=case.id,
                    action="created",
                    performed_by="system",
                    notes=f"Claim flagged by ML pipeline. Combined Score: {res['combined_fraud_score']:.4f}"
                )
                db.add(trail)

    db.commit()

    return {
        "status": "success", 
        "scored_count": len(claims), 
        "flagged_count": flagged_count
    }
