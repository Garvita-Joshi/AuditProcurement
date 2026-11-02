"""
AuditAI — Pydantic schemas for expense fraud pipeline API requests/responses.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# ──────────────────────────────────────────
# Expense Claim Schemas
# ──────────────────────────────────────────

class ExpenseClaimCreate(BaseModel):
    """Schema for creating a single expense claim."""
    claim_id: str
    employee_id: str
    employee_name: str
    claimed_amount: Decimal
    vendor_name: str
    claimed_date: date
    category: Optional[str] = None
    description: Optional[str] = None
    is_fraud: bool = False
    fraud_type: str = "none"


class ExpenseClaimResponse(BaseModel):
    """Schema for returning a single expense claim."""
    id: int
    claim_id: str
    employee_id: str
    employee_name: str
    claimed_amount: Decimal
    vendor_name: str
    claimed_date: date
    category: Optional[str] = None
    description: Optional[str] = None
    status: str
    submitted_at: datetime
    receipt_id: Optional[int] = None
    is_fraud: bool = False
    fraud_type: str = "none"

    # Nested prediction summary (if scored)
    fraud_score: Optional[float] = None
    is_flagged: Optional[bool] = None

    # Multi-entity & Maker-checker details
    entity_name: Optional[str] = None
    currency: Optional[str] = None
    case_status: Optional[str] = None
    closest_vendor_match: Optional[str] = None
    vendor_similarity_score: Optional[float] = None

    class Config:
        from_attributes = True


class ExpenseClaimDetail(BaseModel):
    """Full detail view of a claim including OCR, prediction, and audit report."""
    claim: ExpenseClaimResponse
    ocr_result: Optional["OcrResultResponse"] = None
    prediction: Optional["FraudPredictionResponse"] = None
    audit_report: Optional["AuditReportResponse"] = None

    class Config:
        from_attributes = True


class ClaimListResponse(BaseModel):
    """Paginated list of claims."""
    claims: List[ExpenseClaimResponse]
    total: int
    page: int
    page_size: int


# ──────────────────────────────────────────
# Receipt Schemas
# ──────────────────────────────────────────

class ReceiptResponse(BaseModel):
    """Schema for receipt metadata."""
    id: int
    receipt_id: str
    file_path: str
    file_type: str
    upload_status: str
    uploaded_at: datetime

    class Config:
        from_attributes = True


# ──────────────────────────────────────────
# OCR Result Schemas
# ──────────────────────────────────────────

class OcrResultResponse(BaseModel):
    """Schema for OCR extraction results."""
    id: int
    receipt_id: int
    raw_ocr_text: Optional[str] = None
    extracted_vendor: Optional[str] = None
    extracted_amount: Optional[Decimal] = None
    extracted_date: Optional[str] = None
    extracted_tax_id: Optional[str] = None
    extracted_line_items: Optional[List[Dict[str, Any]]] = None
    extraction_method: str
    extraction_confidence: Optional[float] = None
    processed_at: datetime

    class Config:
        from_attributes = True


# ──────────────────────────────────────────
# Fraud Prediction Schemas
# ──────────────────────────────────────────

class FraudPredictionResponse(BaseModel):
    """Schema for fraud prediction results with all three score layers."""
    id: int
    claim_id: str
    reconstruction_error: Optional[float] = None
    isolation_forest_score: Optional[float] = None
    combined_fraud_score: Optional[float] = None
    is_flagged: bool
    shap_values: Optional[Dict[str, float]] = None
    feature_values: Optional[Dict[str, float]] = None
    predicted_at: datetime

    class Config:
        from_attributes = True


class FraudSummaryResponse(BaseModel):
    """Dashboard-level fraud summary stats."""
    total_claims: int
    flagged_count: int
    fraud_rate: float
    average_score: float
    score_distribution: Dict[str, int]  # Bucketed histogram counts
    recent_flagged: List[ExpenseClaimResponse]
    fraud_over_time: List[Dict[str, Any]]  # [{date: ..., count: ..., rate: ...}]


# ──────────────────────────────────────────
# Audit Report Schemas
# ──────────────────────────────────────────

class AuditReportResponse(BaseModel):
    """Schema for generated audit report."""
    id: int
    claim_id: str
    report_text: str
    generated_by: Optional[str] = None
    generated_at: datetime

    class Config:
        from_attributes = True


# ──────────────────────────────────────────
# Upload Response Schemas
# ──────────────────────────────────────────

class UploadResponse(BaseModel):
    """Generic response for file uploads."""
    status: str
    message: str
    processed_count: int = 0
    error_count: int = 0
    errors: List[Dict[str, Any]] = []


class ScoringResponse(BaseModel):
    """Response after batch or single scoring."""
    status: str
    scored_count: int
    flagged_count: int
    errors: List[str] = []


class EntityResponse(BaseModel):
    id: int
    name: str
    currency: str
    materiality_threshold: Decimal

    class Config:
        from_attributes = True


class CaseAuditTrailResponse(BaseModel):
    id: int
    case_id: int
    action: str
    performed_by: str
    notes: Optional[str] = None
    timestamp: datetime

    class Config:
        from_attributes = True


class CaseResponse(BaseModel):
    id: int
    claim_id: str
    status: str
    maker_id: Optional[str] = None
    checker_id: Optional[str] = None
    maker_notes: Optional[str] = None
    checker_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    claim_amount: Decimal
    vendor_name: str
    employee_name: str
    fraud_score: float

    class Config:
        from_attributes = True
