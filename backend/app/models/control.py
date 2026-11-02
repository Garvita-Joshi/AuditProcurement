"""Persistent control-point, ingestion, and audit-assertion records."""
from datetime import datetime
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from backend.app.db import Base

class ControlPointResult(Base):
    __tablename__ = "control_point_results"
    id = Column(Integer, primary_key=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=True, index=True)
    claim_id = Column(String(50), ForeignKey("expense_claims.claim_id"), nullable=True, index=True)
    control_point_id = Column(String(80), nullable=False, index=True)
    control_point_name = Column(String(160), nullable=False)
    category = Column(String(40), nullable=False)
    status = Column(String(20), nullable=False, index=True)
    confidence = Column(Float, nullable=False)
    explanation_text = Column(Text, nullable=False)
    evidence = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

class ControlPointAssertionMap(Base):
    __tablename__ = "control_point_assertion_map"
    id = Column(Integer, primary_key=True)
    control_point_id = Column(String(80), nullable=False, index=True)
    assertion = Column(String(60), nullable=False, index=True)
    weight = Column(Float, nullable=False, default=1.0)

class IngestionBatch(Base):
    __tablename__ = "ingestion_batches"
    id = Column(Integer, primary_key=True)
    source_name = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    accepted_rows = Column(Integer, nullable=False, default=0)
    rejected_rows = Column(Integer, nullable=False, default=0)
    column_mapping = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
