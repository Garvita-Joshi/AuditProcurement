"""
AuditAI — ORM models for the expense fraud detection pipeline.

These models track the full lifecycle of an expense claim:
  Upload → OCR → Extraction → Feature Engineering → Fraud Scoring → Audit Report
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Text, DateTime, Date,
    ForeignKey, JSON, Numeric, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from backend.app.db import Base
import enum


class ClaimStatus(str, enum.Enum):
    """Lifecycle status of an expense claim."""
    PENDING = "pending"
    PROCESSING = "processing"
    SCORED = "scored"
    FLAGGED = "flagged"
    APPROVED = "approved"
    REJECTED = "rejected"


class UploadStatus(str, enum.Enum):
    """Processing status of an uploaded receipt."""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class ExpenseClaim(Base):
    """
    An employee expense reimbursement claim.

    Each claim may optionally reference a receipt (image/PDF) and will
    accumulate fraud predictions and audit reports as it moves through
    the pipeline.
    """
    __tablename__ = "expense_claims"

    id = Column(Integer, primary_key=True, autoincrement=True)
    claim_id = Column(String(50), unique=True, nullable=False, index=True)
    employee_id = Column(String(50), nullable=False, index=True)
    employee_name = Column(String(200), nullable=False)
    claimed_amount = Column(Numeric(precision=15, scale=2), nullable=False)
    vendor_name = Column(String(300), nullable=False)
    claimed_date = Column(Date, nullable=False, index=True)
    category = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    status = Column(
        String(20),
        nullable=False,
        default=ClaimStatus.PENDING.value,
        index=True,
    )
    submitted_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Optional link to an uploaded receipt
    receipt_id = Column(Integer, ForeignKey("receipts.id"), nullable=True)

    # Link to Entity
    entity_id = Column(Integer, ForeignKey("entities.id"), nullable=True)

    # Ground truth labels (for synthetic data / evaluation)
    is_fraud = Column(Boolean, default=False, nullable=False)
    fraud_type = Column(String(100), default="none", nullable=False)

    # Relationships
    receipt = relationship("Receipt", back_populates="claims", lazy="joined")
    entity = relationship("Entity", back_populates="claims", lazy="joined")
    case = relationship("Case", back_populates="claim", uselist=False)
    prediction = relationship(
        "FraudPrediction",
        back_populates="claim",
        uselist=False,
        lazy="joined",
    )
    audit_report = relationship(
        "AuditReport",
        back_populates="claim",
        uselist=False,
        lazy="joined",
    )


class Receipt(Base):
    """
    An uploaded receipt image or PDF associated with one or more expense claims.
    """
    __tablename__ = "receipts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    receipt_id = Column(String(50), unique=True, nullable=False, index=True)
    file_path = Column(String(500), nullable=False)
    file_type = Column(String(20), nullable=False)  # image/pdf
    upload_status = Column(
        String(20),
        nullable=False,
        default=UploadStatus.UPLOADED.value,
    )
    uploaded_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    claims = relationship("ExpenseClaim", back_populates="receipt")
    ocr_result = relationship(
        "OcrResult",
        back_populates="receipt",
        uselist=False,
        lazy="joined",
    )


class OcrResult(Base):
    """
    OCR extraction output for a receipt.

    Stores both the raw OCR text and the structured fields parsed from it.
    The extraction_method records which engine succeeded (paddleocr/tesseract),
    and extraction_confidence gives a rough quality signal.
    """
    __tablename__ = "ocr_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    receipt_id = Column(Integer, ForeignKey("receipts.id"), unique=True, nullable=False)

    raw_ocr_text = Column(Text, nullable=True)
    extracted_vendor = Column(String(300), nullable=True)
    extracted_amount = Column(Numeric(precision=15, scale=2), nullable=True)
    extracted_date = Column(String(50), nullable=True)
    extracted_tax_id = Column(String(100), nullable=True)
    extracted_line_items = Column(JSON, nullable=True)  # List of {description, qty, amount}

    extraction_method = Column(String(30), nullable=False, default="paddleocr")
    extraction_confidence = Column(Float, nullable=True)
    processed_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationship
    receipt = relationship("Receipt", back_populates="ocr_result")


class FraudPrediction(Base):
    """
    Fraud scoring output for an expense claim.

    Stores the three-layer scoring from the two-stage pipeline:
      1. reconstruction_error — MSE between input features and Autoencoder output
      2. isolation_forest_score — anomaly score from IF trained on reconstructed features
      3. combined_fraud_score — weighted combination of the above

    SHAP values and the input feature vector are stored as JSON for inspection.
    """
    __tablename__ = "fraud_predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    claim_id = Column(
        String(50),
        ForeignKey("expense_claims.claim_id"),
        unique=True,
        nullable=False,
        index=True,
    )

    # Three-layer scores (all stored independently per spec)
    reconstruction_error = Column(Float, nullable=True)
    isolation_forest_score = Column(Float, nullable=True)
    combined_fraud_score = Column(Float, nullable=True)

    is_flagged = Column(Boolean, default=False, nullable=False)

    # Explainability data
    shap_values = Column(JSON, nullable=True)  # {feature_name: shap_value, ...}
    feature_values = Column(JSON, nullable=True)  # {feature_name: raw_value, ...}

    predicted_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationship
    claim = relationship("ExpenseClaim", back_populates="prediction")


class AuditReport(Base):
    """
    LLM-generated audit note for a flagged expense claim.

    Generated by Gemini using the claim data, SHAP explanation, and OCR evidence.
    """
    __tablename__ = "audit_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    claim_id = Column(
        String(50),
        ForeignKey("expense_claims.claim_id"),
        unique=True,
        nullable=False,
        index=True,
    )

    report_text = Column(Text, nullable=False)
    generated_by = Column(String(100), nullable=True)  # e.g. "gemini-2.0-flash"
    generated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationship
    claim = relationship("ExpenseClaim", back_populates="audit_report")


class Entity(Base):
    """
    Operating entity/subsidiary under which expense claims are filed.
    """
    __tablename__ = "entities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False, unique=True)
    currency = Column(String(10), nullable=False, default="INR")
    materiality_threshold = Column(Numeric(precision=15, scale=2), nullable=False, default=50000.00)

    # Relationships
    claims = relationship("ExpenseClaim", back_populates="entity")


class Case(Base):
    """
    Maker-Checker case associated with a flagged expense claim.
    """
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    claim_id = Column(
        String(50),
        ForeignKey("expense_claims.claim_id"),
        unique=True,
        nullable=False,
        index=True,
    )
    status = Column(String(50), nullable=False, default="open")  # open, maker_recommended_approve, maker_recommended_reject, closed_approved, closed_rejected
    maker_id = Column(String(100), nullable=True)
    checker_id = Column(String(100), nullable=True)
    maker_notes = Column(Text, nullable=True)
    checker_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    claim = relationship("ExpenseClaim", back_populates="case")
    audit_trail = relationship("CaseAuditTrail", back_populates="case", cascade="all, delete-orphan")


class CaseAuditTrail(Base):
    """
    Append-only audit trail logging transitions and comments on a case.
    """
    __tablename__ = "case_audit_trails"

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    action = Column(String(100), nullable=False)  # created, recommended_approve, recommended_reject, final_approved, final_rejected, comment
    performed_by = Column(String(100), nullable=False)  # maker, checker, system
    notes = Column(Text, nullable=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationship
    case = relationship("Case", back_populates="audit_trail")
