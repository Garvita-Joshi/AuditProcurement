"""
AuditAI — API endpoints for receipt upload and OCR processing.
"""
import logging
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from backend.app.config import RECEIPTS_DIR
from backend.app.db import get_db
from backend.app.models.expense import ExpenseClaim, OcrResult, Receipt
from backend.app.ocr.engine import ocr_engine
from backend.app.ocr.extractor import extract_fields
from backend.app.ocr.preprocess import preprocess_image
from backend.app.schemas.expense import OcrResultResponse, ReceiptResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/receipts", tags=["Receipts"])


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_receipt(
    file: UploadFile = File(...),
    claim_id: str = None,
    db: Session = Depends(get_db),
):
    """
    Upload a receipt image/PDF, run OCR + extraction, store results.

    Optionally link to a claim via claim_id query parameter.
    """
    if not file.filename:
        raise HTTPException(400, "No file provided.")

    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in ("jpg", "jpeg", "png", "pdf", "tiff", "bmp"):
        raise HTTPException(400, f"Unsupported file type: {ext}")

    # Save file to disk
    receipt_id = f"RCP-{uuid.uuid4().hex[:8].upper()}"
    file_type = "pdf" if ext == "pdf" else "image"
    save_dir = Path(RECEIPTS_DIR)
    save_dir.mkdir(parents=True, exist_ok=True)
    save_path = save_dir / f"{receipt_id}.{ext}"

    try:
        contents = await file.read()
        with open(save_path, "wb") as f:
            f.write(contents)
    except Exception as e:
        raise HTTPException(500, f"Failed to save file: {e}")

    # Create receipt record
    receipt = Receipt(
        receipt_id=receipt_id,
        file_path=str(save_path),
        file_type=file_type,
        upload_status="processing",
    )
    db.add(receipt)
    db.commit()
    db.refresh(receipt)

    # Run OCR pipeline
    try:
        # Preprocess
        preprocessed = preprocess_image(str(save_path))

        if preprocessed is not None:
            # OCR
            raw_text, confidence, method = ocr_engine.extract_text(preprocessed)

            # Structured extraction
            fields = extract_fields(raw_text, use_llm_fallback=True)

            # Store OCR result
            ocr_result = OcrResult(
                receipt_id=receipt.id,
                raw_ocr_text=raw_text,
                extracted_vendor=fields.get("vendor"),
                extracted_amount=fields.get("amount"),
                extracted_date=fields.get("date"),
                extracted_tax_id=fields.get("tax_id"),
                extracted_line_items=fields.get("line_items"),
                extraction_method=method,
                extraction_confidence=fields.get("confidence", confidence),
            )
            db.add(ocr_result)
            receipt.upload_status = "processed"
        else:
            receipt.upload_status = "failed"

    except Exception as e:
        logger.error("OCR processing failed for %s: %s", receipt_id, e)
        receipt.upload_status = "failed"

    # Link to claim if provided
    if claim_id:
        claim = db.query(ExpenseClaim).filter(ExpenseClaim.claim_id == claim_id).first()
        if claim:
            claim.receipt_id = receipt.id

    db.commit()

    return {
        "status": "success",
        "receipt_id": receipt_id,
        "upload_status": receipt.upload_status,
        "file_path": str(save_path),
    }


@router.get("/{receipt_id}", response_model=dict)
def get_receipt(receipt_id: str, db: Session = Depends(get_db)):
    """Get receipt metadata and OCR results."""
    receipt = db.query(Receipt).filter(Receipt.receipt_id == receipt_id).first()
    if not receipt:
        raise HTTPException(404, f"Receipt {receipt_id} not found.")

    ocr_resp = None
    if receipt.ocr_result:
        ocr = receipt.ocr_result
        ocr_resp = {
            "id": ocr.id,
            "raw_ocr_text": ocr.raw_ocr_text,
            "extracted_vendor": ocr.extracted_vendor,
            "extracted_amount": float(ocr.extracted_amount) if ocr.extracted_amount else None,
            "extracted_date": ocr.extracted_date,
            "extracted_tax_id": ocr.extracted_tax_id,
            "extracted_line_items": ocr.extracted_line_items,
            "extraction_method": ocr.extraction_method,
            "extraction_confidence": ocr.extraction_confidence,
        }

    return {
        "receipt_id": receipt.receipt_id,
        "file_path": receipt.file_path,
        "file_type": receipt.file_type,
        "upload_status": receipt.upload_status,
        "uploaded_at": receipt.uploaded_at.isoformat(),
        "ocr_result": ocr_resp,
    }
