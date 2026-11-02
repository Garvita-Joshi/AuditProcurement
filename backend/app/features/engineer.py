"""
AuditAI — Feature engineering for expense claim fraud detection.
Computes 15 features per claim for the two-stage ML pipeline:
  Autoencoder (reconstruction) → Isolation Forest (anomaly scoring)
Features cover mismatch detection, duplicate detection, vendor anomaly checks,
statistical outliers, and temporal patterns.
"""
import logging
import math
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from fuzzywuzzy import fuzz

from backend.app.config import (
    AMOUNT_MISMATCH_THRESHOLD,
    DUPLICATE_SIMILARITY_THRESHOLD,
    HOLIDAYS,
)

logger = logging.getLogger(__name__)

# Deterministic feature name order — used by the ML pipeline
FEATURE_NAMES = [
    "amount_mismatch_ratio",
    "has_amount_mismatch",
    "duplicate_score",
    "is_likely_duplicate",
    "vendor_anomaly_score",
    "is_known_vendor",
    "amount_zscore",
    "claim_frequency_7d",
    "claim_frequency_30d",
    "is_weekend",
    "is_holiday",
    "is_round_amount",
    "amount_log",
    "split_transaction_flag",
    "category_risk_score",
]

# Category → risk score mapping
_CATEGORY_RISK = {
    "client entertainment": 0.7,
    "entertainment": 0.7,
    "travel": 0.5,
    "accommodation": 0.5,
    "meals": 0.4,
    "food": 0.4,
    "transport": 0.4,
    "office supplies": 0.3,
    "supplies": 0.3,
    "utilities": 0.2,
}

# Pre-parse holiday dates
_HOLIDAY_DATES = set()
for h in HOLIDAYS:
    try:
        parts = h.split("-")
        _HOLIDAY_DATES.add(date(int(parts[0]), int(parts[1]), int(parts[2])))
    except (ValueError, IndexError):
        pass

# Converts a date string into a usable Python date object
def _parse_date(d: Any) -> Optional[date]:
    """Safely parse a date from various input types."""
    if isinstance(d, date):
        return d
    if isinstance(d, str):
        try:
            parts = d.split("-")
            return date(int(parts[0]), int(parts[1]), int(parts[2]))
        except (ValueError, IndexError):
            return None
    return None

# Compares claimed amount with OCR receipt amount. Returns mismatch percentage and flag.
def _amount_mismatch(claim: dict) -> Tuple[float, float]:
    """Compute amount mismatch ratio and binary flag."""
    claimed = float(claim.get("claimed_amount", 0) or 0)
    ocr_amt = claim.get("ocr_amount")

    if ocr_amt is None or claimed == 0:
        return (0.0, 0.0)

    ocr_amt = float(ocr_amt)
    ratio = abs(ocr_amt - claimed) / claimed
    flag = 1.0 if ratio > AMOUNT_MISMATCH_THRESHOLD else 0.0
    return (round(ratio, 4), flag)


def _duplicate_score(claim: dict, all_claims: List[dict]) -> Tuple[float, float]:
    """
    Compute max fuzzy-match similarity against all other claims.

    Compares composite string of (vendor_name + amount + date).
    """
    claim_id = claim.get("claim_id", "")
    claim_sig = (
        f"{claim.get('vendor_name', '')}|"
        f"{claim.get('claimed_amount', '')}|"
        f"{claim.get('claimed_date', '')}"
    )

    max_score = 0.0
    for other in all_claims:
        if other.get("claim_id") == claim_id:
            continue
        other_sig = (
            f"{other.get('vendor_name', '')}|"
            f"{other.get('claimed_amount', '')}|"
            f"{other.get('claimed_date', '')}"
        )
        score = fuzz.ratio(claim_sig, other_sig) / 100.0
        if score > max_score:
            max_score = score

    flag = 1.0 if max_score > DUPLICATE_SIMILARITY_THRESHOLD else 0.0
    return (round(max_score, 4), flag)


def _vendor_anomaly(vendor_name: str, known_vendors: List[str]) -> Tuple[float, float]:
    """
    Check if vendor is a typosquatted version of a known vendor.

    vendor_anomaly_score = 1 - max(fuzzy_ratio to any known vendor).
    Higher score = more anomalous.
    """
    if not vendor_name or not known_vendors:
        return (1.0, 0.0)

    vendor_lower = vendor_name.lower().strip()

    # Check exact match first
    known_lower = [v.lower().strip() for v in known_vendors]
    is_known = 1.0 if vendor_lower in known_lower else 0.0

    max_ratio = 0.0
    for known in known_lower:
        ratio = fuzz.ratio(vendor_lower, known) / 100.0
        if ratio > max_ratio:
            max_ratio = ratio

    anomaly_score = round(1.0 - max_ratio, 4)
    return (anomaly_score, is_known)


def _amount_zscore(claim: dict, all_claims: List[dict]) -> float:
    """Z-score of claimed amount vs. all claims from the same employee."""
    emp_id = claim.get("employee_id")
    claimed = float(claim.get("claimed_amount", 0) or 0)

    emp_amounts = [
        float(c.get("claimed_amount", 0) or 0)
        for c in all_claims
        if c.get("employee_id") == emp_id
    ]

    if len(emp_amounts) < 2:
        return 0.0

    mean = np.mean(emp_amounts)
    std = np.std(emp_amounts)

    if std == 0:
        return 0.0

    return round(float((claimed - mean) / std), 4)


def _claim_frequency(
    claim: dict, all_claims: List[dict], days: int
) -> float:
    """Count claims by the same employee within ±`days` of this claim's date."""
    emp_id = claim.get("employee_id")
    claim_date = _parse_date(claim.get("claimed_date"))

    if not claim_date or not emp_id:
        return 0.0

    count = 0
    window = timedelta(days=days)
    for c in all_claims:
        if c.get("employee_id") != emp_id:
            continue
        if c.get("claim_id") == claim.get("claim_id"):
            continue
        c_date = _parse_date(c.get("claimed_date"))
        if c_date and abs((c_date - claim_date).days) <= days:
            count += 1

    return float(count)


def _temporal_features(claim: dict) -> Tuple[float, float]:
    """Check if claim date falls on weekend or known holiday."""
    claim_date = _parse_date(claim.get("claimed_date"))
    if not claim_date:
        return (0.0, 0.0)

    is_weekend = 1.0 if claim_date.weekday() >= 5 else 0.0
    is_holiday = 1.0 if claim_date in _HOLIDAY_DATES else 0.0
    return (is_weekend, is_holiday)


def _is_round_amount(amount: float) -> float:
    """Check if amount is a round number (divisible by 100, 500, or 1000)."""
    if amount <= 0:
        return 0.0
    return 1.0 if (amount % 100 == 0 or amount % 500 == 0 or amount % 1000 == 0) else 0.0


def _split_transaction_flag(claim: dict, all_claims: List[dict]) -> float:
    """Flag if 2+ claims from the same employee exist on the same date."""
    emp_id = claim.get("employee_id")
    claim_date = str(claim.get("claimed_date", ""))

    count = sum(
        1 for c in all_claims
        if c.get("employee_id") == emp_id
        and str(c.get("claimed_date", "")) == claim_date
    )

    return 1.0 if count >= 2 else 0.0


def _category_risk_score(category: str) -> float:
    """Map expense category to a risk score."""
    if not category:
        return 0.2
    return _CATEGORY_RISK.get(category.lower().strip(), 0.2)


def compute_features(
    claim: dict,
    all_claims: List[dict],
    known_vendors: List[str],
) -> Dict[str, float]:
    """
    Compute all 15 fraud detection features for a single expense claim.

    Args:
        claim: Dict with keys: claim_id, employee_id, claimed_amount, vendor_name,
               claimed_date, category, ocr_amount (nullable).
        all_claims: List of all claim dicts (for comparison-based features).
        known_vendors: List of approved/known vendor name strings.

    Returns:
        Dict mapping feature name → float value, in deterministic order.
    """
    claimed_amount = float(claim.get("claimed_amount", 0) or 0)

    mismatch_ratio, has_mismatch = _amount_mismatch(claim)
    dup_score, is_dup = _duplicate_score(claim, all_claims)
    vendor_anomaly, is_known = _vendor_anomaly(
        claim.get("vendor_name", ""), known_vendors
    )
    zscore = _amount_zscore(claim, all_claims)
    freq_7d = _claim_frequency(claim, all_claims, 7)
    freq_30d = _claim_frequency(claim, all_claims, 30)
    is_weekend, is_holiday = _temporal_features(claim)
    round_flag = _is_round_amount(claimed_amount)
    log_amount = round(math.log(claimed_amount + 1), 4) if claimed_amount >= 0 else 0.0
    split_flag = _split_transaction_flag(claim, all_claims)
    cat_risk = _category_risk_score(claim.get("category", ""))

    return {
        "amount_mismatch_ratio": mismatch_ratio,
        "has_amount_mismatch": has_mismatch,
        "duplicate_score": dup_score,
        "is_likely_duplicate": is_dup,
        "vendor_anomaly_score": vendor_anomaly,
        "is_known_vendor": is_known,
        "amount_zscore": zscore,
        "claim_frequency_7d": freq_7d,
        "claim_frequency_30d": freq_30d,
        "is_weekend": is_weekend,
        "is_holiday": is_holiday,
        "is_round_amount": round_flag,
        "amount_log": log_amount,
        "split_transaction_flag": split_flag,
        "category_risk_score": cat_risk,
    }


def compute_features_batch(
    claims: List[dict],
    known_vendors: List[str],
) -> Tuple[List[Dict[str, float]], List[str]]:
    """
    Compute features for all claims in a batch.

    Args:
        claims: List of claim dicts.
        known_vendors: List of approved vendor names.

    Returns:
        Tuple of (list of feature dicts, deterministic list of feature names).
    """
    feature_dicts = []
    for claim in claims:
        features = compute_features(claim, claims, known_vendors)
        feature_dicts.append(features)

    return (feature_dicts, FEATURE_NAMES)
