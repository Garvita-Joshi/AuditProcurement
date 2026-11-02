"""
AuditAI — API endpoints for expense claim management.

Handles claim upload (CSV/JSON), individual claim retrieval, listing with
filtering/sorting/pagination, and receipt attachment.
"""
import io
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from fuzzywuzzy import fuzz
from backend.app.config import KNOWN_VENDORS
from backend.app.db import Base, engine, get_db
from backend.app.models.expense import (
    AuditReport,
    ExpenseClaim,
    FraudPrediction,
    OcrResult,
    Receipt,
    Entity,
    Case,
    CaseAuditTrail,
)
from backend.app.schemas.expense import (
    ClaimListResponse,
    ExpenseClaimDetail,
    ExpenseClaimResponse,
    FraudPredictionResponse,
    AuditReportResponse,
    OcrResultResponse,
    UploadResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/claims", tags=["Claims"])


def get_closest_vendor(vendor_name: str):
    if not vendor_name:
        return None, 0.0
    vendor_lower = vendor_name.lower().strip()
    max_ratio = 0.0
    closest = None
    for known in KNOWN_VENDORS:
        ratio = fuzz.ratio(vendor_lower, known.lower().strip()) / 100.0
        if ratio > max_ratio:
            max_ratio = ratio
            closest = known
    return closest, max_ratio


@router.post("/init-db", status_code=status.HTTP_200_OK)
def init_db(db: Session = Depends(get_db)):
    """Create all database tables and seed default entity."""
    try:
        Base.metadata.create_all(bind=engine)
        
        # Seed default APAC Entity
        entity = db.query(Entity).filter(Entity.name == "APAC Entity").first()
        if not entity:
            entity = Entity(name="APAC Entity", currency="INR", materiality_threshold=50000.00)
            db.add(entity)
            db.commit()
            
        return {"status": "success", "message": "All database tables created & default entity seeded."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB init failed: {e}")


@router.post("/upload", response_model=UploadResponse)
async def upload_claims(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload expense claims from a CSV or JSON file.

    Expected CSV columns: claim_id, employee_id, employee_name, claimed_amount,
    vendor_name, claimed_date, category, description, is_fraud, fraud_type, ocr_amount
    """
    if not file.filename:
        raise HTTPException(400, "No file provided.")

    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in ("csv", "json"):
        raise HTTPException(400, "File must be CSV or JSON.")

    try:
        contents = await file.read()
        if ext == "csv":
            df = pd.read_csv(io.BytesIO(contents))
        else:
            df = pd.read_json(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(422, f"Failed to parse file: {e}")

    # Standardize columns
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    required = ["claim_id", "employee_id", "employee_name", "claimed_amount", "vendor_name", "claimed_date"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise HTTPException(422, f"Missing columns: {missing}")

    loaded = 0
    errors = []

    # Fetch all existing claim IDs at once to avoid N+1 queries
    existing_claim_ids = set(r[0] for r in db.query(ExpenseClaim.claim_id).all())
    
    # Get default entity once
    default_entity = db.query(Entity).filter(Entity.name == "APAC Entity").first()
    entity_id = default_entity.id if default_entity else None

    claims_to_add = []
    for idx, row in df.iterrows():
        try:
            claim_id = str(row["claim_id"]).strip()

            # Skip duplicates using our in-memory set
            if claim_id in existing_claim_ids:
                continue

            # Parse amount
            amt_raw = str(row["claimed_amount"]).replace(",", "").replace("₹", "").replace("$", "").strip()
            amount = Decimal(amt_raw)

            # Parse date
            date_val = pd.to_datetime(row["claimed_date"]).date()

            # Parse fraud labels
            is_fraud = False
            if "is_fraud" in df.columns:
                val = str(row.get("is_fraud", "")).strip().lower()
                is_fraud = val in ("true", "1", "yes", "t")

            fraud_type = str(row.get("fraud_type", "none")).strip() if pd.notna(row.get("fraud_type")) else "none"

            claim = ExpenseClaim(
                claim_id=claim_id,
                employee_id=str(row["employee_id"]).strip(),
                employee_name=str(row["employee_name"]).strip(),
                claimed_amount=amount,
                vendor_name=str(row["vendor_name"]).strip(),
                claimed_date=date_val,
                category=str(row.get("category", "")).strip() if pd.notna(row.get("category")) else None,
                description=str(row.get("description", "")).strip() if pd.notna(row.get("description")) else None,
                status="pending",
                is_fraud=is_fraud,
                fraud_type=fraud_type,
                entity_id=entity_id,
            )
            claims_to_add.append(claim)
            existing_claim_ids.add(claim_id) # prevent duplicate inserts from the same file
            loaded += 1
        except Exception as e:
            errors.append({"row": idx + 1, "error": str(e)})

    if claims_to_add:
        db.add_all(claims_to_add)
        db.commit()

    return UploadResponse(
        status="success" if not errors else "partial_success",
        message=f"Loaded {loaded} claims.",
        processed_count=len(df),
        error_count=len(errors),
        errors=errors[:20],  # Limit error details
    )


@router.get("", response_model=ClaimListResponse)
def list_claims(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    sort_by: str = Query("submitted_at", regex="^(claim_id|employee_name|vendor_name|claimed_amount|claimed_date|submitted_at|status)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    """List claims with filtering, sorting, and pagination."""
    query = db.query(ExpenseClaim)

    if status_filter:
        query = query.filter(ExpenseClaim.status == status_filter)

    # Sorting
    sort_col = getattr(ExpenseClaim, sort_by, ExpenseClaim.submitted_at)
    if sort_order == "desc":
        query = query.order_by(sort_col.desc())
    else:
        query = query.order_by(sort_col.asc())

    total = query.count()
    claims = query.offset((page - 1) * page_size).limit(page_size).all()

    claim_responses = []
    for c in claims:
        closest_match, match_ratio = get_closest_vendor(c.vendor_name)
        if match_ratio >= 1.0 or match_ratio < 0.70:
            closest_match = None
            match_ratio = 0.0

        resp = ExpenseClaimResponse(
            id=c.id,
            claim_id=c.claim_id,
            employee_id=c.employee_id,
            employee_name=c.employee_name,
            claimed_amount=c.claimed_amount,
            vendor_name=c.vendor_name,
            claimed_date=c.claimed_date,
            category=c.category,
            description=c.description,
            status=c.status,
            submitted_at=c.submitted_at,
            receipt_id=c.receipt_id,
            is_fraud=c.is_fraud,
            fraud_type=c.fraud_type,
            fraud_score=c.prediction.combined_fraud_score if c.prediction else None,
            is_flagged=c.prediction.is_flagged if c.prediction else None,
            entity_name=c.entity.name if c.entity else "APAC Entity",
            currency=c.entity.currency if c.entity else "INR",
            case_status=c.case.status if c.case else "none",
            closest_vendor_match=closest_match,
            vendor_similarity_score=match_ratio if closest_match else None,
        )
        claim_responses.append(resp)

    return ClaimListResponse(
        claims=claim_responses,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{claim_id}")
def get_claim_detail(claim_id: str, db: Session = Depends(get_db)):
    """Get full claim detail with OCR, prediction, SHAP, and audit report."""
    claim = db.query(ExpenseClaim).filter(ExpenseClaim.claim_id == claim_id).first()
    if not claim:
        raise HTTPException(404, f"Claim {claim_id} not found.")

    # Build response
    closest_match, match_ratio = get_closest_vendor(claim.vendor_name)
    if match_ratio >= 1.0 or match_ratio < 0.70:
        closest_match = None
        match_ratio = 0.0

    claim_resp = ExpenseClaimResponse(
        id=claim.id,
        claim_id=claim.claim_id,
        employee_id=claim.employee_id,
        employee_name=claim.employee_name,
        claimed_amount=claim.claimed_amount,
        vendor_name=claim.vendor_name,
        claimed_date=claim.claimed_date,
        category=claim.category,
        description=claim.description,
        status=claim.status,
        submitted_at=claim.submitted_at,
        receipt_id=claim.receipt_id,
        is_fraud=claim.is_fraud,
        fraud_type=claim.fraud_type,
        fraud_score=claim.prediction.combined_fraud_score if claim.prediction else None,
        is_flagged=claim.prediction.is_flagged if claim.prediction else None,
        entity_name=claim.entity.name if claim.entity else "APAC Entity",
        currency=claim.entity.currency if claim.entity else "INR",
        case_status=claim.case.status if claim.case else "none",
        closest_vendor_match=closest_match,
        vendor_similarity_score=match_ratio if closest_match else None,
    )

    ocr_resp = None
    if claim.receipt and claim.receipt.ocr_result:
        ocr = claim.receipt.ocr_result
        ocr_resp = OcrResultResponse(
            id=ocr.id,
            receipt_id=ocr.receipt_id,
            raw_ocr_text=ocr.raw_ocr_text,
            extracted_vendor=ocr.extracted_vendor,
            extracted_amount=ocr.extracted_amount,
            extracted_date=ocr.extracted_date,
            extracted_tax_id=ocr.extracted_tax_id,
            extracted_line_items=ocr.extracted_line_items,
            extraction_method=ocr.extraction_method,
            extraction_confidence=ocr.extraction_confidence,
            processed_at=ocr.processed_at,
        )

    pred_resp = None
    if claim.prediction:
        p = claim.prediction
        pred_resp = FraudPredictionResponse(
            id=p.id,
            claim_id=p.claim_id,
            reconstruction_error=p.reconstruction_error,
            isolation_forest_score=p.isolation_forest_score,
            combined_fraud_score=p.combined_fraud_score,
            is_flagged=p.is_flagged,
            shap_values=p.shap_values,
            feature_values=p.feature_values,
            predicted_at=p.predicted_at,
        )

    report_resp = None
    if claim.audit_report:
        r = claim.audit_report
        report_resp = AuditReportResponse(
            id=r.id,
            claim_id=r.claim_id,
            report_text=r.report_text,
            generated_by=r.generated_by,
            generated_at=r.generated_at,
        )

    return {
        "claim": claim_resp,
        "ocr_result": ocr_resp,
        "prediction": pred_resp,
        "audit_report": report_resp,
    }


@router.patch("/{claim_id}/status")
def update_claim_status(
    claim_id: str,
    new_status: str = Query(..., regex="^(pending|processing|scored|flagged|approved|rejected)$"),
    db: Session = Depends(get_db),
):
    """Update a claim's status (approve, reject, flag)."""
    claim = db.query(ExpenseClaim).filter(ExpenseClaim.claim_id == claim_id).first()
    if not claim:
        raise HTTPException(404, f"Claim {claim_id} not found.")

    claim.status = new_status
    db.commit()
    return {"status": "success", "claim_id": claim_id, "new_status": new_status}
