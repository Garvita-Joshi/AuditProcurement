"""
AuditAI — API endpoints for generating LLM audit reports.
"""
import logging
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db import get_db
from backend.app.llm.gemini import generate_audit_report
from backend.app.models.expense import AuditReport, ExpenseClaim

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/reports", tags=["Reports"])


@router.post("/generate/{claim_id}", status_code=status.HTTP_201_CREATED)
def generate_report_for_claim(claim_id: str, db: Session = Depends(get_db)):
    """Generate an audit report for a specific flagged claim."""
    claim = db.query(ExpenseClaim).filter(ExpenseClaim.claim_id == claim_id).first()
    if not claim:
        raise HTTPException(404, f"Claim {claim_id} not found.")

    if claim.status not in ("flagged", "rejected"):
        raise HTTPException(400, "Can only generate reports for flagged or rejected claims.")

    if not claim.prediction:
        raise HTTPException(400, "Claim has no fraud prediction.")

    # Prepare data for LLM
    claim_data = {
        "claim_id": claim.claim_id,
        "employee_name": claim.employee_name,
        "vendor_name": claim.vendor_name,
        "claimed_amount": float(claim.claimed_amount),
        "claimed_date": str(claim.claimed_date),
        "category": claim.category,
        "combined_fraud_score": claim.prediction.combined_fraud_score,
    }

    ocr_evidence = {}
    if claim.receipt and claim.receipt.ocr_result:
        ocr = claim.receipt.ocr_result
        ocr_evidence = {
            "extracted_vendor": ocr.extracted_vendor,
            "extracted_amount": float(ocr.extracted_amount) if ocr.extracted_amount else None,
            "extracted_date": ocr.extracted_date,
            "raw_ocr_text": ocr.raw_ocr_text[:500],  # truncate to save tokens
        }

    shap_explanation = claim.prediction.shap_values or {}

    try:
        report_text = generate_audit_report(claim_data, shap_explanation, ocr_evidence)
    except Exception as e:
        logger.error("Failed to generate report for %s: %s", claim_id, e)
        raise HTTPException(500, f"Failed to generate report: {e}")

    # Save to DB
    if claim.audit_report:
        claim.audit_report.report_text = report_text
    else:
        report = AuditReport(
            claim_id=claim.claim_id,
            report_text=report_text,
            generated_by="gemini-2.0-flash",
        )
        db.add(report)

    db.commit()

    return {"status": "success", "claim_id": claim_id, "report": report_text}


@router.post("/generate-all", status_code=status.HTTP_200_OK)
def generate_reports_for_all_flagged(db: Session = Depends(get_db)):
    """Generate audit reports for all flagged claims that don't have one."""
    flagged_claims = (
        db.query(ExpenseClaim)
        .filter(ExpenseClaim.status == "flagged")
        .outerjoin(AuditReport)
        .filter(AuditReport.id == None)
        .all()
    )

    if not flagged_claims:
        return {"status": "success", "message": "No flagged claims need reports.", "generated_count": 0}

    generated_count = 0
    for claim in flagged_claims:
        if not claim.prediction:
            continue
            
        claim_data = {
            "claim_id": claim.claim_id,
            "employee_name": claim.employee_name,
            "vendor_name": claim.vendor_name,
            "claimed_amount": float(claim.claimed_amount),
            "claimed_date": str(claim.claimed_date),
            "category": claim.category,
            "combined_fraud_score": claim.prediction.combined_fraud_score,
        }

        ocr_evidence = {}
        if claim.receipt and claim.receipt.ocr_result:
            ocr = claim.receipt.ocr_result
            ocr_evidence = {
                "extracted_vendor": ocr.extracted_vendor,
                "extracted_amount": float(ocr.extracted_amount) if ocr.extracted_amount else None,
                "extracted_date": ocr.extracted_date,
            }

        shap_explanation = claim.prediction.shap_values or {}

        try:
            report_text = generate_audit_report(claim_data, shap_explanation, ocr_evidence)
            report = AuditReport(
                claim_id=claim.claim_id,
                report_text=report_text,
                generated_by="gemini",
            )
            db.add(report)
            generated_count += 1
        except Exception as e:
            logger.error("Failed to generate report for %s: %s", claim.claim_id, e)

    db.commit()
    return {"status": "success", "generated_count": generated_count}
