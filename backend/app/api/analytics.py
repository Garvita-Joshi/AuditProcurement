"""
AuditAI — API endpoints for advanced audit analytics, Benford's Law, and SoD screening.
"""
import logging
import math
from collections import Counter
from typing import Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.db import get_db
from backend.app.models.expense import Case, CaseAuditTrail, ExpenseClaim

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/analytics", tags=["Analytics"])


@router.get("/benford")
def get_benford_law_distribution(db: Session = Depends(get_db)):
    """
    Computes the actual frequency of first digits of all claim amounts
    versus the logarithmic expectation of Benford's Law.
    """
    claims = db.query(ExpenseClaim).all()
    if not claims:
        # The frontend chart expects a list in both populated and empty states.
        return []

    # Extract first digit of amounts
    digits = []
    for c in claims:
        amt = float(c.claimed_amount)
        if amt <= 0:
            continue
        # Get first digit
        first_digit = int(str(amt).replace(".", "").replace("0", "").strip()[0])
        if 1 <= first_digit <= 9:
            digits.append(first_digit)

    counts = Counter(digits)
    total = len(digits) if digits else 1

    benford_expected = {d: math.log10(1 + 1/d) * 100 for d in range(1, 10)}
    actual_dist = {d: (counts.get(d, 0) / total) * 100 for d in range(1, 10)}

    chart_data = []
    for d in range(1, 10):
        chart_data.append({
            "digit": str(d),
            "actual": round(actual_dist[d], 2),
            "expected": round(benford_expected[d], 2)
        })

    return chart_data


@router.get("/related-parties")
def screen_related_parties(db: Session = Depends(get_db)):
    """
    Screens for potential related-party transactions.
    
    Heuristic: Checks if the vendor name contains parts of the employee's name/surname
    (excluding generic words like 'local', 'taxi', etc.).
    """
    claims = db.query(ExpenseClaim).all()
    flagged = []

    stop_words = {"the", "and", "a", "an", "mr", "mrs", "dr", "inc", "co", "corp", "ltd", "pvt"}

    for c in claims:
        emp_parts = [p.lower().strip() for p in c.employee_name.split() if p.lower().strip() not in stop_words]
        vendor_lower = c.vendor_name.lower()

        # Simple check: does the vendor name contain any significant employee name parts?
        matched_words = []
        for part in emp_parts:
            if len(part) >= 3 and part in vendor_lower:
                matched_words.append(part)

        if matched_words:
            # Avoid crash if prediction is missing
            score = c.prediction.combined_fraud_score if c.prediction else 0.0
            flagged.append({
                "claim_id": c.claim_id,
                "employee_name": c.employee_name,
                "vendor_name": c.vendor_name,
                "claimed_amount": float(c.claimed_amount),
                "claimed_date": c.claimed_date.isoformat(),
                "matched_terms": matched_words,
                "fraud_score": score
            })

    return flagged


@router.get("/sod-violations")
def screen_sod_violations(db: Session = Depends(get_db)):
    """
    Screens for Segregation of Duties (SoD) violations.
    
    Heuristic:
    - Maker == Checker on case reviews.
    - Employee == Maker (submitting claims and also investigating/recommending them).
    - Employee == Checker (submitting claims and also performing final approval).
    """
    cases = db.query(Case).all()
    violations = []

    for c in cases:
        claim = c.claim
        
        # Check Maker == Checker
        if c.maker_id and c.checker_id and c.maker_id == c.checker_id:
            violations.append({
                "claim_id": c.claim_id,
                "employee_name": claim.employee_name,
                "type": "Maker and Checker are the same user",
                "user_involved": c.maker_id,
                "details": f"User '{c.maker_id}' reviewed as Maker and signed off as Checker."
            })

        # Check Employee == Maker
        # In a real app we'd map user IDs, here we check name/ID matching
        if c.maker_id and (c.maker_id.lower() in claim.employee_name.lower() or c.maker_id == claim.employee_id):
            violations.append({
                "claim_id": c.claim_id,
                "employee_name": claim.employee_name,
                "type": "Claimant is Maker",
                "user_involved": c.maker_id,
                "details": f"Employee '{claim.employee_name}' acted as Maker to recommend their own claim."
            })

        # Check Employee == Checker
        if c.checker_id and (c.checker_id.lower() in claim.employee_name.lower() or c.checker_id == claim.employee_id):
            violations.append({
                "claim_id": c.claim_id,
                "employee_name": claim.employee_name,
                "type": "Claimant is Checker",
                "user_involved": c.checker_id,
                "details": f"Employee '{claim.employee_name}' acted as Checker to sign off on their own claim."
            })

    return violations


@router.get("/case-metrics")
def get_case_cycle_metrics(db: Session = Depends(get_db)):
    """
    Computes case cycle statistics:
    - Average time-to-disposition (in seconds).
    - False-positive rate trend (claims flagged that checkers marked as approved).
    """
    closed_cases = db.query(Case).filter(Case.status.in_(["closed_approved", "closed_rejected"])).all()
    
    total_time = 0.0
    count = len(closed_cases)
    
    for c in closed_cases:
        duration = (c.updated_at - c.created_at).total_seconds()
        total_time += max(0.0, duration)

    avg_time = total_time / count if count > 0 else 0.0

    # False-positive rate: closed_approved cases over total closed cases
    # (Since approved means they were flagged by ML but determined to be normal/valid by auditors)
    false_positives = sum(1 for c in closed_cases if c.status == "closed_approved")
    fp_rate = (false_positives / count) * 100 if count > 0 else 0.0

    return {
        "avg_time_to_disposition_seconds": round(avg_time, 1),
        "false_positive_rate": round(fp_rate, 2),
        "total_disposed_cases": count
    }
