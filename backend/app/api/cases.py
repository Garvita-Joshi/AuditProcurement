"""
AuditAI — API endpoints for Maker-Checker case management and audit trails.
"""
import logging
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.db import get_db
from backend.app.models.expense import Case, CaseAuditTrail, ExpenseClaim
from backend.app.schemas.expense import CaseAuditTrailResponse, CaseResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/cases", tags=["Cases"])


@router.get("", response_model=List[CaseResponse])
def list_cases(
    status_filter: str = Query(None, alias="status"),
    db: Session = Depends(get_db)
):
    """List all active or closed investigation cases."""
    query = db.query(Case).join(ExpenseClaim)
    
    if status_filter:
        query = query.filter(Case.status == status_filter)
        
    cases = query.all()
    
    response = []
    for c in cases:
        # Avoid crash if prediction is missing
        fraud_score = c.claim.prediction.combined_fraud_score if c.claim.prediction else 0.0
        response.append({
            "id": c.id,
            "claim_id": c.claim_id,
            "status": c.status,
            "maker_id": c.maker_id,
            "checker_id": c.checker_id,
            "maker_notes": c.maker_notes,
            "checker_notes": c.checker_notes,
            "created_at": c.created_at,
            "updated_at": c.updated_at,
            "claim_amount": c.claim.claimed_amount,
            "vendor_name": c.claim.vendor_name,
            "employee_name": c.claim.employee_name,
            "fraud_score": fraud_score
        })
    return response


@router.post("/{claim_id}/maker-recommend", status_code=status.HTTP_200_OK)
def maker_recommend(
    claim_id: str,
    action: str = Query(..., regex="^(approve|reject)$"),
    notes: str = Query(..., min_length=5),
    maker_id: str = Query("Default Maker"),
    db: Session = Depends(get_db)
):
    """
    Maker action: Review the flagged claim and recommend either approval or rejection.
    """
    case = db.query(Case).filter(Case.claim_id == claim_id).first()
    if not case:
        # Create case if missing (auto-heal)
        claim = db.query(ExpenseClaim).filter(ExpenseClaim.claim_id == claim_id).first()
        if not claim:
            raise HTTPException(404, f"Claim {claim_id} not found.")
        case = Case(claim_id=claim_id, status="open")
        db.add(case)
        db.commit()
        db.refresh(case)

    if case.status not in ("open", "maker_recommended_approve", "maker_recommended_reject"):
        raise HTTPException(400, f"Cannot perform Maker action on a case with status {case.status}.")

    new_status = "maker_recommended_approve" if action == "approve" else "maker_recommended_reject"
    case.status = new_status
    case.maker_id = maker_id
    case.maker_notes = notes
    case.updated_at = datetime.utcnow()

    # Append to audit trail
    trail_action = "recommended_approve" if action == "approve" else "recommended_reject"
    trail = CaseAuditTrail(
        case_id=case.id,
        action=trail_action,
        performed_by="maker",
        notes=notes
    )
    db.add(trail)
    
    # Update claim status
    case.claim.status = "processing"
    
    db.commit()
    return {"status": "success", "message": f"Maker successfully recommended {action}."}


@router.post("/{claim_id}/checker-signoff", status_code=status.HTTP_200_OK)
def checker_signoff(
    claim_id: str,
    action: str = Query(..., regex="^(approve|reject)$"),
    notes: str = Query(..., min_length=5),
    checker_id: str = Query("Default Checker"),
    db: Session = Depends(get_db)
):
    """
    Checker action: Final sign-off. Approve or reject the claim, closing the case.
    """
    case = db.query(Case).filter(Case.claim_id == claim_id).first()
    if not case:
        raise HTTPException(404, f"Case for claim {claim_id} not found.")

    if case.status not in ("maker_recommended_approve", "maker_recommended_reject", "open"):
        raise HTTPException(400, f"Cannot sign-off on a case with status {case.status}.")

    if checker_id == case.maker_id:
        raise HTTPException(400, "Segregation of Duties Violation: Checker cannot be the same person as Maker.")

    new_status = "closed_approved" if action == "approve" else "closed_rejected"
    case.status = new_status
    case.checker_id = checker_id
    case.checker_notes = notes
    case.updated_at = datetime.utcnow()

    # Append to audit trail
    trail_action = "final_approved" if action == "approve" else "final_rejected"
    trail = CaseAuditTrail(
        case_id=case.id,
        action=trail_action,
        performed_by="checker",
        notes=notes
    )
    db.add(trail)
    
    # Update claim status
    case.claim.status = "approved" if action == "approve" else "rejected"
    
    db.commit()
    return {"status": "success", "message": f"Checker final sign-off complete. Claim {action}d."}


@router.get("/{claim_id}/trail", response_model=List[CaseAuditTrailResponse])
def get_case_audit_trail(claim_id: str, db: Session = Depends(get_db)):
    """Fetch the append-only audit trail for a case."""
    case = db.query(Case).filter(Case.claim_id == claim_id).first()
    if not case:
        return []
    return db.query(CaseAuditTrail).filter(CaseAuditTrail.case_id == case.id).order_by(CaseAuditTrail.timestamp.asc()).all()
