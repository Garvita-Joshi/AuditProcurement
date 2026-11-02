import pytest
from datetime import date
from backend.app.features.engineer import (
    _amount_mismatch, _duplicate_score, _vendor_anomaly,
    _amount_zscore, _temporal_features, _split_transaction_flag, _is_round_amount
)

# --- Test amount mismatch ---
def test_amount_mismatch_detected():
    claim = {'claimed_amount': 1000, 'ocr_amount': 500}
    ratio, flag = _amount_mismatch(claim)
    assert ratio == 0.5
    assert flag == 1.0

def test_no_mismatch_close_amounts():
    claim = {'claimed_amount': 1000, 'ocr_amount': 980}
    ratio, flag = _amount_mismatch(claim)
    assert ratio == 0.02
    assert flag == 0.0

def test_no_mismatch_when_ocr_missing():
    claim = {'claimed_amount': 1000, 'ocr_amount': None}
    ratio, flag = _amount_mismatch(claim)
    assert ratio == 0.0
    assert flag == 0.0

# --- Test duplicate detection ---
def test_duplicate_detected():
    claims = [
        {'claim_id': 'C1', 'vendor_name': 'Starbucks', 'claimed_amount': 500, 'claimed_date': date(2025, 4, 1)},
        {'claim_id': 'C2', 'vendor_name': 'Starbucks', 'claimed_amount': 500, 'claimed_date': date(2025, 4, 2)},
    ]
    score, flag = _duplicate_score(claims[0], claims)
    assert score > 0.85
    assert flag == 1.0

def test_no_duplicate_different_vendor():
    claims = [
        {'claim_id': 'C1', 'vendor_name': 'Starbucks', 'claimed_amount': 500, 'claimed_date': date(2025, 4, 1)},
        {'claim_id': 'C2', 'vendor_name': 'Amazon', 'claimed_amount': 500, 'claimed_date': date(2025, 4, 1)},
    ]
    score, flag = _duplicate_score(claims[0], claims)
    assert score < 0.85
    assert flag == 0.0

# --- Test vendor anomaly ---
def test_typosquatted_vendor_flagged():
    known = ['Amazon', 'Starbucks', 'Uber']
    score, is_known = _vendor_anomaly('Amazn', known)
    assert 0 < score < 1  # A typo is not an exact match; do not impose an arbitrary fuzzy-distance cutoff.
    assert is_known == 0.0

def test_known_vendor_exact_match():
    known = ['Amazon', 'Starbucks']
    score, is_known = _vendor_anomaly('Amazon', known)
    assert score == 0.0
    assert is_known == 1.0

# --- Test z-score ---
def test_amount_zscore_normal():
    claims = [{'employee_id': 'E1', 'claimed_amount': a} for a in [100, 100, 100, 100, 100]]
    z = _amount_zscore(claims[0], claims)
    assert z == 0.0

def test_amount_zscore_outlier():
    claims = [{'employee_id': 'E1', 'claimed_amount': a} for a in [100, 100, 100, 100, 10000]]
    # The last one should be a significant outlier
    z = _amount_zscore(claims[-1], claims)
    assert z > 1.5

# --- Test temporal features ---
def test_weekend_flag():
    # Saturday date
    claim_sat = {'claimed_date': date(2025, 4, 5)}
    is_weekend, _ = _temporal_features(claim_sat)
    assert is_weekend == 1.0

    # Monday date
    claim_mon = {'claimed_date': date(2025, 4, 7)}
    is_weekend, _ = _temporal_features(claim_mon)
    assert is_weekend == 0.0

def test_holiday_flag():
    # Using 2025-01-26 as a known holiday from config if loaded, but we'll mock it
    from backend.app.features.engineer import _HOLIDAY_DATES
    _HOLIDAY_DATES.add(date(2025, 1, 26))
    
    claim_holiday = {'claimed_date': date(2025, 1, 26)}
    _, is_holiday = _temporal_features(claim_holiday)
    assert is_holiday == 1.0

# --- Test split transactions ---
def test_split_transaction_detected():
    claims = [
        {'employee_id': 'E1', 'claimed_amount': 4500, 'claimed_date': date(2025, 4, 1)},
        {'employee_id': 'E1', 'claimed_amount': 4800, 'claimed_date': date(2025, 4, 1)},
    ]
    assert _split_transaction_flag(claims[0], claims) == 1.0

def test_no_split_different_dates():
    claims = [
        {'employee_id': 'E1', 'claimed_amount': 4500, 'claimed_date': date(2025, 4, 1)},
        {'employee_id': 'E1', 'claimed_amount': 4800, 'claimed_date': date(2025, 4, 5)},
    ]
    assert _split_transaction_flag(claims[0], claims) == 0.0

# --- Test round amount ---
def test_round_amount_detected():
    assert _is_round_amount(5000) == 1.0
    assert _is_round_amount(500) == 1.0
    assert _is_round_amount(5001) == 0.0
